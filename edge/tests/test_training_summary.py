from datetime import datetime, timedelta, timezone

import pytest

from qmzg_edge.training.models import TrainingSummary
from qmzg_edge.training.summary import build_tuya_property_values


def valid_summary(**overrides: object) -> TrainingSummary:
    started = datetime(2026, 8, 11, 1, 0, tzinfo=timezone.utc)
    values = {
        "session_id": "demo_session_001",
        "started_at": started,
        "ended_at": started + timedelta(seconds=623),
        "duration_sec": 623,
        "total_reps": 57,
        "avg_confidence": 9670,
        "max_elbow_angle": 1285,
        "max_shoulder_angle": 934,
        "actions": {"curl": 20, "raise": 15, "lateral": 12, "boxing": 10},
        "fault_count": 0,
    }
    values.update(overrides)
    return TrainingSummary(**values)


def test_training_summary_maps_to_tuya_boundary_names() -> None:
    fields = build_tuya_property_values(valid_summary())

    assert fields["training_session_id"] == "demo_session_001"
    assert fields["training_avg_confidence"] == 9670
    assert fields["training_max_shldr_angle"] == 934
    assert "training_max_shoulder_angle" not in fields


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("avg_confidence", 10001),
        ("max_elbow_angle", 1801),
        ("max_shoulder_angle", -1),
        ("duration_sec", 86401),
        ("total_reps", 100001),
    ],
)
def test_training_summary_rejects_tuya_range_violations(field: str, value: int) -> None:
    with pytest.raises(ValueError):
        valid_summary(**{field: value})


def test_training_summary_rejects_inconsistent_duration() -> None:
    with pytest.raises(ValueError, match="duration"):
        valid_summary(duration_sec=600)


def test_training_summary_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone"):
        valid_summary(started_at=datetime(2026, 8, 11, 1, 0))

