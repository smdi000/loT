from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.integrations.tuya.parser import normalize_tuya_message
from app.main import app
from app.models import Device, TrainingSession
from app.services.training import NormalizedTrainingSummary, create_training_session, training_summary_from_tuya_message


@pytest.fixture
def client(session):
    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def register_and_login(client: TestClient, email: str, password: str = "correct-horse-42") -> str:
    registered = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )
    assert registered.status_code == 201
    logged_in = client.post("/api/auth/login", json={"email": email, "password": password})
    assert logged_in.status_code == 200
    return logged_in.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def add_device(session, device_id: str) -> None:
    session.add(Device(id=device_id, product_id="product-test"))
    session.commit()


def summary(
    device_id: str,
    external_session_id: str = "acceptance_session_001",
    tuya_msg_id: str | None = "tuya-training-001",
    extras: dict | None = None,
) -> NormalizedTrainingSummary:
    started_at = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
    payload = {
        "actions": {"biceps_curl": 20, "arm_raise": 15, "lateral_raise": 12, "boxing": 10},
        "fault_count": 0,
        "device_status": "idle",
    }
    if extras:
        payload.update(extras)
    return NormalizedTrainingSummary(
        external_session_id=external_session_id,
        device_id=device_id,
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=623),
        duration_sec=623,
        total_reps=57,
        avg_confidence=9670,
        max_elbow_angle=1284,
        max_shoulder_angle=1148,
        summary_json=payload,
        source_type="mock",
        tuya_msg_id=tuya_msg_id,
    )


def test_register_login_me_and_wrong_password(client: TestClient) -> None:
    token = register_and_login(client, "athlete@example.test")
    me = client.get("/api/me", headers=headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "athlete@example.test"
    wrong = client.post("/api/auth/login", json={"email": "athlete@example.test", "password": "wrong-pass"})
    assert wrong.status_code == 401


def test_device_binding_is_single_owner(client: TestClient, session) -> None:
    add_device(session, "device-bind-01")
    first = register_and_login(client, "first@example.test")
    second = register_and_login(client, "second@example.test")

    bound = client.post("/api/devices/bind", json={"device_id": "device-bind-01"}, headers=headers(first))
    assert bound.status_code == 201
    assert client.get("/api/devices", headers=headers(first)).json()[0]["id"] == "device-bind-01"
    assert client.post("/api/devices/bind", json={"device_id": "device-bind-01"}, headers=headers(first)).status_code == 409
    assert client.post("/api/devices/bind", json={"device_id": "device-bind-01"}, headers=headers(second)).status_code == 409
    assert client.delete("/api/devices/device-bind-01/bind", headers=headers(first)).status_code == 204
    assert client.post("/api/devices/bind", json={"device_id": "device-bind-01"}, headers=headers(second)).status_code == 201


def test_training_session_auto_assigns_owner_is_idempotent_and_reports(client: TestClient, session) -> None:
    add_device(session, "device-training-01")
    token = register_and_login(client, "trainer@example.test")
    assert client.post("/api/devices/bind", json={"device_id": "device-training-01"}, headers=headers(token)).status_code == 201

    first = create_training_session(session, summary("device-training-01", extras={"future_metric": {"score": 5}}))
    repeated = create_training_session(session, summary("device-training-01"))
    assert first.created is True
    assert repeated.created is False
    assert session.query(TrainingSession).count() == 1
    assert first.session.user_id == client.get("/api/me", headers=headers(token)).json()["id"]

    history = client.get("/api/training-sessions?page=1&page_size=10", headers=headers(token))
    assert history.status_code == 200
    assert history.json()["total"] == 1
    session_id = history.json()["items"][0]["id"]
    detail = client.get(f"/api/training-sessions/{session_id}", headers=headers(token))
    assert detail.status_code == 200
    report = client.get(f"/api/training-sessions/{session_id}/report", headers=headers(token))
    assert report.status_code == 200
    body = report.json()
    assert body["duration_sec"] == 623
    assert body["total_reps"] == 57
    assert body["avg_confidence"] == 96.7
    assert body["range_of_motion"] == {"elbow_max": 128.4, "shoulder_max": 114.8}
    assert body["summary_json"]["future_metric"] == {"score": 5}
    assert "not a medical diagnosis" in body["notice"]


def test_unbound_session_is_retained_and_private_users_are_isolated(client: TestClient, session) -> None:
    add_device(session, "device-unbound-01")
    unbound = create_training_session(session, summary("device-unbound-01", "unbound_session_001", "tuya-unbound-001"))
    assert unbound.created is True
    assert unbound.session.user_id is None

    add_device(session, "device-private-01")
    owner = register_and_login(client, "owner@example.test")
    other = register_and_login(client, "other@example.test")
    assert client.post("/api/devices/bind", json={"device_id": "device-private-01"}, headers=headers(owner)).status_code == 201
    private_session = create_training_session(session, summary("device-private-01", "private_session_001", "tuya-private-001"))
    assert private_session.session.user_id is not None

    assert client.get("/api/training-sessions", headers=headers(other)).json()["total"] == 0
    assert client.get(f"/api/training-sessions/{private_session.session.id}", headers=headers(other)).status_code == 404


def test_training_service_rejects_unknown_device_and_invalid_time(session) -> None:
    with pytest.raises(ValueError, match="device_id does not exist"):
        create_training_session(session, summary("missing-device"))

    add_device(session, "device-invalid-time")
    invalid = summary("device-invalid-time", "invalid_time_001", "tuya-invalid-time")
    object.__setattr__(invalid, "ended_at", invalid.started_at - timedelta(seconds=1))
    with pytest.raises(ValueError, match="ended_at"):
        create_training_session(session, invalid)


def test_tuya_event_adapter_produces_a_business_summary_without_raw_json_parsing() -> None:
    normalized_message = normalize_tuya_message(
        {
            "bizCode": "deviceEventMessage",
            "dataId": "tuya-event-adapter-001",
            "devId": "device-adapter-01",
            "eventCode": "training_completed",
            "outputParams": {
                "session_id": "acceptance_session_001",
                "started_at": 1_786_156_800_000,
                "ended_at": 1_786_157_423_000,
                "duration_sec": 623,
                "total_reps": 57,
                "avg_confidence": 9670,
                "max_elbow_angle": 1284,
                "max_shoulder_angle": 1148,
                "summary_json": '{"actions":{"biceps_curl":20},"future_metric":"kept"}',
            },
        }
    )
    adapted = training_summary_from_tuya_message(normalized_message)
    assert adapted is not None
    assert adapted.external_session_id == "acceptance_session_001"
    assert adapted.device_id == "device-adapter-01"
    assert adapted.summary_json["future_metric"] == "kept"
    assert adapted.source_type == "tuya_event"
