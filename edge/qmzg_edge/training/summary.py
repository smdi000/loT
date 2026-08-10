from __future__ import annotations

import json

from .models import TrainingSummary


TUYA_TRAINING_FIELDS = {
    "session_id": "training_session_id",
    "started_at": "training_started_at",
    "ended_at": "training_ended_at",
    "duration_sec": "training_duration_sec",
    "total_reps": "training_total_reps",
    "avg_confidence": "training_avg_confidence",
    "max_elbow_angle": "training_max_elbow_angle",
    # The abbreviation exists only at the Tuya adapter boundary.
    "max_shoulder_angle": "training_max_shldr_angle",
    "summary_json": "training_summary_json",
}


def build_tuya_property_values(summary: TrainingSummary) -> dict[str, object]:
    compact_summary = json.dumps(summary.summary_json, separators=(",", ":"), ensure_ascii=False)
    return {
        TUYA_TRAINING_FIELDS["session_id"]: summary.session_id,
        TUYA_TRAINING_FIELDS["started_at"]: summary.started_at_ms,
        TUYA_TRAINING_FIELDS["ended_at"]: summary.ended_at_ms,
        TUYA_TRAINING_FIELDS["duration_sec"]: summary.duration_sec,
        TUYA_TRAINING_FIELDS["total_reps"]: summary.total_reps,
        TUYA_TRAINING_FIELDS["avg_confidence"]: summary.avg_confidence,
        TUYA_TRAINING_FIELDS["max_elbow_angle"]: summary.max_elbow_angle,
        TUYA_TRAINING_FIELDS["max_shoulder_angle"]: summary.max_shoulder_angle,
        TUYA_TRAINING_FIELDS["summary_json"]: compact_summary,
    }
