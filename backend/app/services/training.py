from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.tuya.parser import NormalizedTuyaMessage
from app.models import Device, TrainingSession, UserDevice

TrainingSource = Literal["tuya_property", "tuya_event", "mock"]
TrainingType = Literal["passive_assist", "resistance", "active_assist"]
_ALLOWED_SOURCES = {"tuya_property", "tuya_event", "mock"}
_ALLOWED_TRAINING_TYPES = {"passive_assist", "resistance", "active_assist"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NormalizedTrainingSummary:
    """Business-facing training record, independent of Tuya wire JSON."""

    external_session_id: str
    device_id: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int
    total_reps: int
    avg_confidence: int
    max_elbow_angle: int
    max_shoulder_angle: int
    summary_json: dict[str, Any]
    source_type: TrainingSource
    training_type: TrainingType | None = None
    tuya_msg_id: str | None = None


@dataclass(frozen=True)
class TrainingSessionResult:
    session: TrainingSession
    created: bool


def training_summary_from_tuya_message(message: NormalizedTuyaMessage) -> NormalizedTrainingSummary | None:
    """Adapt an already-normalized Tuya Event; never parse raw MQTT JSON here."""

    if message.biz_code != "deviceEventMessage" or message.event_code != "training_completed":
        return None
    if not message.device_id:
        return None
    params = message.output_params
    session_id = params.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    summary = params.get("summary_json", {})
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except json.JSONDecodeError:
            summary = {"raw": summary}
    if not isinstance(summary, dict):
        summary = {"raw": summary}
    try:
        return NormalizedTrainingSummary(
            external_session_id=session_id,
            device_id=message.device_id,
            started_at=_datetime_value(params.get("started_at")),
            ended_at=_datetime_value(params.get("ended_at")),
            duration_sec=_int_value(params.get("duration_sec")),
            total_reps=_int_value(params.get("total_reps")),
            avg_confidence=_int_value(params.get("avg_confidence")),
            max_elbow_angle=_int_value(params.get("max_elbow_angle")),
            max_shoulder_angle=_int_value(params.get("max_shoulder_angle")),
            summary_json=summary,
            source_type="tuya_event",
            training_type=training_type_from_summary(summary),
            tuya_msg_id=message.tuya_msg_id,
        )
    except (TypeError, ValueError):
        return None


def training_summary_from_property_message(
    message: NormalizedTuyaMessage,
) -> NormalizedTrainingSummary | None:
    """Adapt the temporary full Property-report workaround at the Tuya boundary.

    The business model deliberately retains ``max_shoulder_angle``.  Only the
    Tuya property identifier is shortened to ``training_max_shldr_angle`` to
    meet the platform's 25-character identifier limit.
    """

    if message.biz_code != "devicePropertyMessage" or not message.device_id:
        return None

    values = message.properties
    required = {
        "training_session_id",
        "training_started_at",
        "training_ended_at",
        "training_duration_sec",
        "training_total_reps",
        "training_avg_confidence",
        "training_max_elbow_angle",
        "training_max_shldr_angle",
        "training_summary_json",
    }
    if not required.issubset(values):
        return None

    session_id = values["training_session_id"]
    if not isinstance(session_id, str) or not session_id.strip():
        return None

    summary = values["training_summary_json"]
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except json.JSONDecodeError:
            summary = {"raw": summary}
    if not isinstance(summary, dict):
        summary = {"raw": summary}

    try:
        return NormalizedTrainingSummary(
            external_session_id=session_id,
            device_id=message.device_id,
            started_at=_datetime_value(values["training_started_at"]),
            ended_at=_datetime_value(values["training_ended_at"]),
            duration_sec=_int_value(values["training_duration_sec"]),
            total_reps=_int_value(values["training_total_reps"]),
            avg_confidence=_int_value(values["training_avg_confidence"]),
            max_elbow_angle=_int_value(values["training_max_elbow_angle"]),
            max_shoulder_angle=_int_value(values["training_max_shldr_angle"]),
            summary_json=summary,
            source_type="tuya_property",
            training_type=training_type_from_summary(summary),
            tuya_msg_id=message.tuya_msg_id,
        )
    except (TypeError, ValueError):
        return None


def _datetime_value(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=UTC)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a training number")
    return int(value)


def training_type_from_summary(summary: dict[str, Any]) -> TrainingType | None:
    """Return the canonical session mode without making it ingestion-critical."""

    value = summary.get("training_type", summary.get("training_mode"))
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _ALLOWED_TRAINING_TYPES:
            return normalized  # type: ignore[return-value]
    logger.warning("Unsupported training type ignored: %r", value)
    return None


def _validate(summary: NormalizedTrainingSummary) -> None:
    if not summary.external_session_id.strip() or len(summary.external_session_id) > 128:
        raise ValueError("external_session_id is required and must be at most 128 characters")
    if not summary.device_id.strip():
        raise ValueError("device_id is required")
    if summary.source_type not in _ALLOWED_SOURCES:
        raise ValueError("unsupported training source")
    if summary.training_type is not None and summary.training_type not in _ALLOWED_TRAINING_TYPES:
        raise ValueError("unsupported training type")
    limits = {
        "duration_sec": (summary.duration_sec, 0, 86_400),
        "total_reps": (summary.total_reps, 0, 100_000),
        "avg_confidence": (summary.avg_confidence, 0, 10_000),
        "max_elbow_angle": (summary.max_elbow_angle, 0, 1_800),
        "max_shoulder_angle": (summary.max_shoulder_angle, 0, 1_800),
    }
    for name, (value, low, high) in limits.items():
        if not low <= value <= high:
            raise ValueError(f"{name} must be between {low} and {high}")
    if (summary.started_at is None) != (summary.ended_at is None):
        raise ValueError("started_at and ended_at must be supplied together")
    if summary.started_at and summary.ended_at:
        elapsed = (summary.ended_at - summary.started_at).total_seconds()
        if elapsed < 0:
            raise ValueError("ended_at must not precede started_at")
        allowed_error = max(60, summary.duration_sec * 0.10)
        if abs(elapsed - summary.duration_sec) > allowed_error:
            raise ValueError("duration_sec differs unreasonably from the timestamp interval")


def create_training_session(session: Session, summary: NormalizedTrainingSummary) -> TrainingSessionResult:
    """Create an idempotent training session and associate the current device owner."""

    _validate(summary)
    device = session.get(Device, summary.device_id)
    if device is None:
        raise ValueError("device_id does not exist")

    existing = session.scalar(
        select(TrainingSession).where(
            TrainingSession.device_id == summary.device_id,
            TrainingSession.external_session_id == summary.external_session_id,
        )
    )
    if existing is None and summary.tuya_msg_id:
        existing = session.scalar(
            select(TrainingSession).where(TrainingSession.tuya_msg_id == summary.tuya_msg_id)
        )
    if existing is not None:
        return TrainingSessionResult(session=existing, created=False)

    binding = session.scalar(select(UserDevice).where(UserDevice.device_id == summary.device_id))
    record = TrainingSession(
        external_session_id=summary.external_session_id,
        user_id=binding.user_id if binding else None,
        device_id=summary.device_id,
        started_at=summary.started_at,
        ended_at=summary.ended_at,
        duration_sec=summary.duration_sec,
        total_reps=summary.total_reps,
        avg_confidence=summary.avg_confidence,
        max_elbow_angle=summary.max_elbow_angle,
        max_shoulder_angle=summary.max_shoulder_angle,
        summary_json=summary.summary_json,
        training_type=summary.training_type,
        source_type=summary.source_type,
        tuya_msg_id=summary.tuya_msg_id,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return TrainingSessionResult(session=record, created=True)
