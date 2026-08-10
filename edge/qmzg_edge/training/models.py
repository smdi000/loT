from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping


class TrainingSummaryError(ValueError):
    """Raised when a completed training session cannot be safely reported."""


def _unix_milliseconds(value: datetime) -> int:
    if value.tzinfo is None or value.utcoffset() is None:
        raise TrainingSummaryError("started_at and ended_at must be timezone-aware")
    return int(value.timestamp() * 1000)


@dataclass(frozen=True)
class TrainingSummary:
    session_id: str
    started_at: datetime
    ended_at: datetime
    duration_sec: int
    total_reps: int
    avg_confidence: int
    max_elbow_angle: int
    max_shoulder_angle: int
    actions: Mapping[str, int]
    fault_count: int = 0

    def __post_init__(self) -> None:
        session_id = self.session_id.strip()
        if not session_id or len(session_id.encode("utf-8")) > 64:
            raise TrainingSummaryError("session_id must contain 1 to 64 UTF-8 bytes")
        object.__setattr__(self, "session_id", session_id)
        start_ms = _unix_milliseconds(self.started_at)
        end_ms = _unix_milliseconds(self.ended_at)
        if end_ms < start_ms:
            raise TrainingSummaryError("ended_at must not precede started_at")
        if not 0 <= self.duration_sec <= 86400:
            raise TrainingSummaryError("duration_sec must be between 0 and 86400")
        measured_duration = (end_ms - start_ms) / 1000
        if abs(measured_duration - self.duration_sec) > 5:
            raise TrainingSummaryError("duration_sec differs from timestamps by more than 5 seconds")
        if not 0 <= self.total_reps <= 100000:
            raise TrainingSummaryError("total_reps must be between 0 and 100000")
        if not 0 <= self.avg_confidence <= 10000:
            raise TrainingSummaryError("avg_confidence must be between 0 and 10000")
        for name, angle in (
            ("max_elbow_angle", self.max_elbow_angle),
            ("max_shoulder_angle", self.max_shoulder_angle),
        ):
            if not 0 <= angle <= 1800:
                raise TrainingSummaryError(f"{name} must be between 0 and 1800")
        if self.fault_count < 0:
            raise TrainingSummaryError("fault_count must not be negative")
        normalized_actions: dict[str, int] = {}
        for action, count in self.actions.items():
            code = str(action).strip()
            if not code or not isinstance(count, int) or count < 0:
                raise TrainingSummaryError("actions must map non-empty codes to non-negative integers")
            normalized_actions[code] = count
        object.__setattr__(self, "actions", MappingProxyType(normalized_actions))
        compact = json.dumps(self.summary_json, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(compact) > 255:
            raise TrainingSummaryError("training_summary_json exceeds the Tuya 255-byte limit")

    @property
    def started_at_ms(self) -> int:
        return _unix_milliseconds(self.started_at)

    @property
    def ended_at_ms(self) -> int:
        return _unix_milliseconds(self.ended_at)

    @property
    def summary_json(self) -> dict[str, object]:
        return {"actions": dict(self.actions), "fault_count": self.fault_count}

    @classmethod
    def demo(cls) -> "TrainingSummary":
        ended = datetime(2026, 8, 11, 4, 10, 23, tzinfo=timezone.utc)
        started = datetime(2026, 8, 11, 4, 0, 0, tzinfo=timezone.utc)
        return cls(
            session_id="demo_session_001",
            started_at=started,
            ended_at=ended,
            duration_sec=623,
            total_reps=57,
            avg_confidence=9670,
            max_elbow_angle=1285,
            max_shoulder_angle=934,
            actions={"curl": 20, "raise": 15, "lateral": 12, "boxing": 10},
            fault_count=0,
        )
