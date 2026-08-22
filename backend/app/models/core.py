from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None
json_type = JSON().with_variant(JSONB, "postgresql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Device(Base):
    __tablename__ = "devices"

    # Tuya Device ID is the natural key so inbound messages can be stored before a user binds it.
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    product_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    users: Mapped[list["UserDevice"]] = relationship(back_populates="device")


class UserDevice(Base):
    __tablename__ = "user_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_user_devices_user_device"),
        UniqueConstraint("device_id", name="uq_user_devices_device_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device: Mapped[Device] = relationship(back_populates="users")


class TuyaMessage(Base):
    __tablename__ = "tuya_messages"
    __table_args__ = (
        UniqueConstraint("tuya_msg_id", name="uq_tuya_messages_tuya_msg_id"),
        UniqueConstraint("dedup_key", name="uq_tuya_messages_dedup_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tuya_msg_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False)
    biz_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_json: Mapped[JsonValue] = mapped_column(json_type, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class TrainingSession(Base):
    __tablename__ = "training_sessions"
    __table_args__ = (
        UniqueConstraint("device_id", "external_session_id", name="uq_training_sessions_device_external"),
        UniqueConstraint("tuya_msg_id", name="uq_training_sessions_tuya_msg_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_elbow_angle: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_shoulder_angle: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary_json: Mapped[JsonValue] = mapped_column(json_type, nullable=False, default=dict)
    training_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tuya_msg_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
