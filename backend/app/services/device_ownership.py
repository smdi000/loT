from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Device, TrainingSession, User, UserDevice

logger = logging.getLogger(__name__)


class DeviceOwnershipError(ValueError):
    """Base error for a rejected internal ownership operation."""


class DeviceNotFoundError(DeviceOwnershipError):
    pass


class TargetUserNotFoundError(DeviceOwnershipError):
    pass


@dataclass(frozen=True)
class DeviceOwnershipPreview:
    device_id: str
    old_user_id: str | None
    new_user_id: str


@dataclass(frozen=True)
class DeviceOwnershipTransferResult(DeviceOwnershipPreview):
    changed: bool


def mask_device_id(device_id: str) -> str:
    if len(device_id) <= 8:
        return f"****{device_id[-4:]}"
    return f"{device_id[:4]}******{device_id[-4:]}"


def preview_device_transfer(
    session: Session,
    *,
    device_id: str,
    to_user_id: str,
) -> DeviceOwnershipPreview:
    """Validate exact identifiers and return current ownership without mutation."""

    normalized_device_id = device_id.strip()
    normalized_user_id = to_user_id.strip()
    if session.get(Device, normalized_device_id) is None:
        raise DeviceNotFoundError("device does not exist")
    if session.get(User, normalized_user_id) is None:
        raise TargetUserNotFoundError("target user does not exist")
    binding = session.scalar(select(UserDevice).where(UserDevice.device_id == normalized_device_id))
    return DeviceOwnershipPreview(
        device_id=normalized_device_id,
        old_user_id=binding.user_id if binding else None,
        new_user_id=normalized_user_id,
    )


def transfer_device(
    session: Session,
    *,
    device_id: str,
    to_user_id: str,
) -> DeviceOwnershipTransferResult:
    """Atomically transfer one device and its archived sessions to one exact user.

    The unique constraint on ``user_devices.device_id`` remains the final
    database guard ensuring that a device has at most one owner.
    """

    try:
        preview = preview_device_transfer(session, device_id=device_id, to_user_id=to_user_id)
        binding = session.scalar(
            select(UserDevice)
            .where(UserDevice.device_id == preview.device_id)
            .with_for_update()
        )
        if binding is not None and binding.user_id == preview.new_user_id:
            session.rollback()
            return DeviceOwnershipTransferResult(**preview.__dict__, changed=False)

        if binding is None:
            session.add(UserDevice(user_id=preview.new_user_id, device_id=preview.device_id))
        else:
            binding.user_id = preview.new_user_id

        # TrainingSession.user_id is the denormalized ownership snapshot used
        # by exports and diagnostics. Keep it consistent with API visibility,
        # which is governed by the current user_devices relation.
        session.execute(
            update(TrainingSession)
            .where(TrainingSession.device_id == preview.device_id)
            .values(user_id=preview.new_user_id)
        )
        session.commit()
    except (DeviceOwnershipError, SQLAlchemyError):
        session.rollback()
        raise

    event = {
        "event": "device_ownership_transfer",
        "device_id": mask_device_id(preview.device_id),
        "old_user_id": preview.old_user_id,
        "new_user_id": preview.new_user_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "operator": "internal_cli",
    }
    logger.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
    return DeviceOwnershipTransferResult(**preview.__dict__, changed=True)
