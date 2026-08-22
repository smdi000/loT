from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.integrations.tuya.parser import normalize_tuya_message
from app.models import Device, TrainingSession, User, UserDevice
from app.services import training as training_service
from app.services.training import training_summary_from_property_message
from scripts.seed_competition_history import DEMO_SESSIONS, seed_competition_history


def property_message(training_type: str | None = None, *, alias: bool = False) -> dict:
    summary = {"actions": {"curl": 20}, "fault_count": 0}
    if training_type is not None:
        summary["training_mode" if alias else "training_type"] = training_type
    import json

    return {
        "bizCode": "devicePropertyMessage",
        "bizData": {
            "dataId": "type-parser-001",
            "devId": "type-device-001",
            "properties": [
                {"code": "training_session_id", "value": "type_session_001"},
                {"code": "training_started_at", "value": 1_786_156_800_000},
                {"code": "training_ended_at", "value": 1_786_157_423_000},
                {"code": "training_duration_sec", "value": 623},
                {"code": "training_total_reps", "value": 20},
                {"code": "training_avg_confidence", "value": 9670},
                {"code": "training_max_elbow_angle", "value": 1285},
                {"code": "training_max_shldr_angle", "value": 934},
                {"code": "training_summary_json", "value": json.dumps(summary)},
            ],
        },
    }


def test_valid_training_type_and_alias_are_normalized() -> None:
    direct = training_summary_from_property_message(normalize_tuya_message(property_message("active_assist")))
    alias = training_summary_from_property_message(
        normalize_tuya_message(property_message("resistance", alias=True))
    )
    assert direct is not None and direct.training_type == "active_assist"
    assert alias is not None and alias.training_type == "resistance"


def test_unknown_training_type_becomes_null_without_losing_session(monkeypatch) -> None:
    warnings: list[tuple] = []
    monkeypatch.setattr(training_service.logger, "warning", lambda *args: warnings.append(args))
    adapted = training_summary_from_property_message(normalize_tuya_message(property_message("not-a-mode")))
    assert adapted is not None
    assert adapted.training_type is None
    assert warnings and warnings[0][0] == "Unsupported training type ignored: %r"


def test_demo_seed_is_idempotent_and_preserves_existing_real_session(session) -> None:
    device = Device(id="seed-device-001", product_id="seed-product")
    owner = User(email="seed-owner@example.test", display_name="Seed Owner", password_hash="hash")
    session.add_all([device, owner])
    session.commit()
    session.add(UserDevice(user_id=owner.id, device_id=device.id))
    started = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
    real = TrainingSession(
        external_session_id="acceptance_cloud_training_001",
        user_id=owner.id,
        device_id=device.id,
        started_at=started,
        ended_at=started + timedelta(seconds=623),
        duration_sec=623,
        total_reps=57,
        avg_confidence=9670,
        max_elbow_angle=1285,
        max_shoulder_angle=934,
        summary_json={"actions": {"curl": 20}},
        training_type=None,
        source_type="tuya_property",
        tuya_msg_id="real-message-001",
    )
    session.add(real)
    session.commit()

    dry_create, dry_skip = seed_competition_history(session, device.id)
    assert (dry_create, dry_skip) == (14, 0)
    assert session.scalar(select(func.count()).select_from(TrainingSession)) == 1

    created, skipped = seed_competition_history(session, device.id, apply=True)
    assert (created, skipped) == (14, 0)
    created_again, skipped_again = seed_competition_history(session, device.id, apply=True)
    assert (created_again, skipped_again) == (0, 14)
    assert session.scalar(select(func.count()).select_from(TrainingSession)) == 15

    preserved = session.scalar(
        select(TrainingSession).where(TrainingSession.external_session_id == "acceptance_cloud_training_001")
    )
    assert preserved is not None
    assert (preserved.duration_sec, preserved.total_reps, preserved.avg_confidence) == (623, 57, 9670)
    assert (preserved.max_elbow_angle, preserved.max_shoulder_angle) == (1285, 934)
    assert preserved.source_type == "tuya_property"
    assert preserved.training_type is None
    assert preserved.user_id == owner.id

    demos = list(session.scalars(select(TrainingSession).where(TrainingSession.source_type == "mock")))
    assert len(demos) == len(DEMO_SESSIONS) == 14
    assert {item.user_id for item in demos} == {owner.id}
    assert sum(item.training_type == "active_assist" for item in demos) == 5
    assert sum(item.training_type == "resistance" for item in demos) == 5
    assert sum(item.training_type == "passive_assist" for item in demos) == 4
