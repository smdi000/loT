from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app
from app.models import Device, TrainingSession, UserDevice
from app.services.device_ownership import (
    DeviceNotFoundError,
    TargetUserNotFoundError,
    transfer_device,
)


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


def register(client: TestClient, email: str) -> tuple[str, str]:
    password = "transfer-test-password"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )
    assert response.status_code == 201
    token = client.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return response.json()["id"], token


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def add_training(session, *, device_id: str, user_id: str) -> TrainingSession:
    started = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    record = TrainingSession(
        external_session_id="transfer-session-001",
        user_id=user_id,
        device_id=device_id,
        started_at=started,
        ended_at=started + timedelta(seconds=623),
        duration_sec=623,
        total_reps=57,
        avg_confidence=9670,
        max_elbow_angle=1285,
        max_shoulder_angle=934,
        summary_json={"actions": {"curl": 20}, "fault_count": 0},
        source_type="mock",
        tuya_msg_id="transfer-message-001",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def test_transfer_owner_a_to_b_changes_api_visibility_without_duplicates(client, session) -> None:
    old_id, old_token = register(client, "old-owner@example.test")
    new_id, new_token = register(client, "new-owner@example.test")
    session.add(Device(id="device-transfer-01", product_id="product-test"))
    session.add(UserDevice(user_id=old_id, device_id="device-transfer-01"))
    session.commit()
    training = add_training(session, device_id="device-transfer-01", user_id=old_id)

    result = transfer_device(session, device_id="device-transfer-01", to_user_id=new_id)

    assert result.changed is True
    assert result.old_user_id == old_id
    assert result.new_user_id == new_id
    bindings = session.query(UserDevice).filter_by(device_id="device-transfer-01").all()
    assert len(bindings) == 1
    assert bindings[0].user_id == new_id
    session.refresh(training)
    assert training.user_id == new_id
    assert client.get("/api/devices", headers=auth(old_token)).json() == []
    assert client.get("/api/training-sessions", headers=auth(old_token)).json()["total"] == 0
    assert client.get("/api/devices", headers=auth(new_token)).json()[0]["id"] == "device-transfer-01"
    assert client.get("/api/training-sessions", headers=auth(new_token)).json()["total"] == 1
    assert client.get(f"/api/training-sessions/{training.id}", headers=auth(new_token)).status_code == 200


def test_transfer_rejects_missing_device_and_target_user(client, session) -> None:
    user_id, _ = register(client, "target@example.test")
    with pytest.raises(DeviceNotFoundError, match="device does not exist"):
        transfer_device(session, device_id="missing-device", to_user_id=user_id)

    session.add(Device(id="device-no-target", product_id="product-test"))
    session.commit()
    with pytest.raises(TargetUserNotFoundError, match="target user does not exist"):
        transfer_device(session, device_id="device-no-target", to_user_id="missing-user")


def test_transfer_to_current_owner_is_idempotent(client, session) -> None:
    user_id, _ = register(client, "same-owner@example.test")
    session.add(Device(id="device-same-owner", product_id="product-test"))
    session.add(UserDevice(user_id=user_id, device_id="device-same-owner"))
    session.commit()

    result = transfer_device(session, device_id="device-same-owner", to_user_id=user_id)

    assert result.changed is False
    assert session.query(UserDevice).filter_by(device_id="device-same-owner").count() == 1
