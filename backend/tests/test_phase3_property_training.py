from __future__ import annotations

from sqlalchemy import func, select

from app.integrations.tuya.parser import normalize_tuya_message
from app.models import Device, TrainingSession, TuyaMessage, User, UserDevice
from app.services.training import training_summary_from_property_message
from app.services.tuya_ingest import ingest_tuya_message


def complete_property_summary(*, message_id: str = "property-summary-001") -> dict:
    """Use the actual Message Service bizData/properties envelope shape."""

    return {
        "bizCode": "devicePropertyMessage",
        "bizData": {
            "dataId": message_id,
            "devId": "device-property-training-01",
            "productId": "product-property-training-01",
            "properties": [
                {"code": "training_session_id", "value": "acceptance_real_training_001"},
                {"code": "training_started_at", "value": 1_786_156_800_000},
                {"code": "training_ended_at", "value": 1_786_157_423_000},
                {"code": "training_duration_sec", "value": 623},
                {"code": "training_total_reps", "value": 57},
                {"code": "training_avg_confidence", "value": 9670},
                {"code": "training_max_elbow_angle", "value": 1285},
                # This is intentionally the Tuya-only <=25 character identifier.
                {"code": "training_max_shldr_angle", "value": 934},
                {
                    "code": "training_summary_json",
                    "value": '{"actions":{"curl":20,"raise":15,"lateral":12,"boxing":10},"fault_count":0}',
                },
                {"code": "future_property", "value": "kept in raw message only"},
            ],
        },
        "ts": 1_786_157_423_000,
    }


def test_complete_property_summary_normalizes_at_the_tuya_boundary() -> None:
    summary = training_summary_from_property_message(normalize_tuya_message(complete_property_summary()))

    assert summary is not None
    assert summary.external_session_id == "acceptance_real_training_001"
    assert summary.max_elbow_angle == 1285
    assert summary.max_shoulder_angle == 934
    assert summary.summary_json["actions"]["boxing"] == 10
    assert summary.source_type == "tuya_property"


def test_missing_property_keeps_raw_message_but_does_not_create_session(session) -> None:
    raw = complete_property_summary()
    raw["bizData"]["properties"] = raw["bizData"]["properties"][:-1]
    raw["bizData"]["properties"] = [
        entry for entry in raw["bizData"]["properties"] if entry["code"] != "training_avg_confidence"
    ]

    result = ingest_tuya_message(session, raw)

    assert result.created is True
    assert result.processed is True
    assert session.scalar(select(func.count()).select_from(TuyaMessage)) == 1
    assert session.scalar(select(func.count()).select_from(TrainingSession)) == 0


def test_property_summary_creates_owner_assigned_session_and_is_idempotent(session) -> None:
    device = Device(id="device-property-training-01", product_id="product-property-training-01")
    owner = User(email="property-owner@example.test", display_name="Property Owner", password_hash="hash")
    session.add_all([device, owner])
    session.commit()
    session.add(UserDevice(user_id=owner.id, device_id=device.id))
    session.commit()

    first = ingest_tuya_message(session, complete_property_summary())
    second = ingest_tuya_message(session, complete_property_summary())

    record = session.scalar(select(TrainingSession))
    assert first.created is True
    assert second.created is False
    assert record is not None
    assert record.user_id == owner.id
    assert record.external_session_id == "acceptance_real_training_001"
    assert record.duration_sec == 623
    assert record.total_reps == 57
    assert record.avg_confidence == 9670
    assert record.max_shoulder_angle == 934
    assert record.source_type == "tuya_property"
    assert session.scalar(select(func.count()).select_from(TrainingSession)) == 1
    assert session.scalar(select(func.count()).select_from(TuyaMessage)) == 1


def test_unknown_property_does_not_make_an_incomplete_summary_valid() -> None:
    raw = complete_property_summary()
    raw["bizData"]["properties"] = [
        entry for entry in raw["bizData"]["properties"] if entry["code"] != "training_summary_json"
    ]
    raw["bizData"]["properties"].append({"code": "unrelated", "value": 1})

    assert training_summary_from_property_message(normalize_tuya_message(raw)) is None
