from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.tuya.parser import NormalizedTuyaMessage, normalize_tuya_message
from app.models import Device, TuyaMessage
from app.services.training import (
    create_training_session,
    training_summary_from_property_message,
    training_summary_from_tuya_message,
)


@dataclass(frozen=True)
class IngestResult:
    message_id: str
    created: bool
    processed: bool


def _ensure_device(session: Session, message: NormalizedTuyaMessage) -> None:
    if not message.device_id:
        return
    device = session.get(Device, message.device_id)
    if device is None:
        session.add(Device(id=message.device_id, product_id=message.product_id))
    elif message.product_id and not device.product_id:
        device.product_id = message.product_id


def _create_training_session_if_supported(session: Session, message: NormalizedTuyaMessage) -> bool:
    """Adapt a normalized Tuya boundary message; raw JSON parsing stays upstream."""

    summary = training_summary_from_tuya_message(message)
    if summary is None:
        summary = training_summary_from_property_message(message)
    if summary is None:
        return False
    create_training_session(session, summary)
    return True


def ingest_tuya_message(session: Session, raw_message: dict[str, Any]) -> IngestResult:
    """Persist first, then parse. Duplicate messages remain idempotent."""

    normalized = normalize_tuya_message(raw_message)
    existing = session.scalar(select(TuyaMessage).where(TuyaMessage.dedup_key == normalized.dedup_key))
    if existing:
        return IngestResult(existing.id, created=False, processed=existing.processed)

    _ensure_device(session, normalized)
    record = TuyaMessage(
        tuya_msg_id=normalized.tuya_msg_id,
        dedup_key=normalized.dedup_key,
        biz_code=normalized.biz_code,
        device_id=normalized.device_id,
        product_id=normalized.product_id,
        event_time=normalized.event_time,
        payload_json=normalized.raw,
        processed=False,
    )
    session.add(record)
    session.flush()  # Raw message now has a durable identity before business parsing.

    if normalized.biz_code == "devicePropertyMessage":
        _create_training_session_if_supported(session, normalized)
        record.processed = True
    elif _create_training_session_if_supported(session, normalized):
        record.processed = True

    session.commit()
    return IngestResult(record.id, created=True, processed=record.processed)
