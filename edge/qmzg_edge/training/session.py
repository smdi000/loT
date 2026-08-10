from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from .models import TrainingSummary


class TrainingSessionAccumulator:
    """Keeps high-frequency inference results local until session completion."""

    def __init__(self, session_id: str, started_at: datetime | None = None) -> None:
        self.session_id = session_id
        self.started_at = started_at or datetime.now(timezone.utc)
        self.reps = 0
        self.confidence_sum = 0
        self.confidence_samples = 0
        self.max_elbow_angle = 0
        self.max_shoulder_angle = 0
        self.actions: Counter[str] = Counter()
        self.fault_count = 0

    def record_inference(
        self,
        *,
        action: str | None,
        confidence: int,
        elbow_angle: int,
        shoulder_angle: int,
        completed_rep: bool = False,
        fault: bool = False,
    ) -> None:
        self.confidence_sum += confidence
        self.confidence_samples += 1
        self.max_elbow_angle = max(self.max_elbow_angle, elbow_angle)
        self.max_shoulder_angle = max(self.max_shoulder_angle, shoulder_angle)
        if completed_rep:
            self.reps += 1
            if action:
                self.actions[action] += 1
        if fault:
            self.fault_count += 1

    def finish(self, ended_at: datetime | None = None) -> TrainingSummary:
        end = ended_at or datetime.now(timezone.utc)
        duration = max(0, round((end - self.started_at).total_seconds()))
        average = round(self.confidence_sum / self.confidence_samples) if self.confidence_samples else 0
        return TrainingSummary(
            session_id=self.session_id,
            started_at=self.started_at,
            ended_at=end,
            duration_sec=duration,
            total_reps=self.reps,
            avg_confidence=average,
            max_elbow_angle=self.max_elbow_angle,
            max_shoulder_angle=self.max_shoulder_angle,
            actions=dict(self.actions),
            fault_count=self.fault_count,
        )
