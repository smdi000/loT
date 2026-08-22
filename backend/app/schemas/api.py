from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=72)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("a valid email address is required")
        return normalized


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=72)


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None
    display_name: str | None
    created_at: datetime
    updated_at: datetime | None


class DeviceBindRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)


class DeviceBindRead(BaseModel):
    device_id: str
    bound: bool


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str | None
    display_name: str | None
    created_at: datetime
    updated_at: datetime | None


class TuyaMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tuya_msg_id: str | None
    biz_code: str
    device_id: str | None
    product_id: str | None
    event_time: datetime | None
    payload_json: Any
    received_at: datetime
    processed: bool


class TrainingSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    external_session_id: str
    user_id: str | None
    device_id: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int | None
    total_reps: int | None
    avg_confidence: int | None
    max_elbow_angle: int | None
    max_shoulder_angle: int | None
    summary_json: Any
    training_type: str | None
    source_type: str
    tuya_msg_id: str | None
    created_at: datetime


class TrainingSessionPage(BaseModel):
    items: list[TrainingSessionRead]
    page: int
    page_size: int
    total: int


class TrainingReport(BaseModel):
    id: str
    device_id: str
    training_time: datetime | None
    duration_sec: int
    total_reps: int
    avg_confidence: float
    range_of_motion: dict[str, float]
    actions: list[dict[str, Any]]
    device_status: str | None
    fault_count: int | None
    training_type: str | None
    summary_json: Any
    notice: str
