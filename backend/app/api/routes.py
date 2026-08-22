from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models import Device, TrainingSession, TuyaMessage, User, UserDevice
from app.schemas import (
    AccessToken,
    DeviceBindRead,
    DeviceBindRequest,
    DeviceRead,
    LoginRequest,
    RegisterRequest,
    TrainingReport,
    TrainingSessionPage,
    TrainingSessionRead,
    TuyaMessageRead,
    UserRead,
)
from app.security.auth import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter()


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "database": "ok"}


@router.post("/api/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: Session = Depends(get_session)) -> User:
    if session.scalar(select(User).where(User.email == payload.email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email is already registered")
    try:
        user = User(
            email=payload.email,
            display_name=payload.display_name,
            password_hash=hash_password(payload.password),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email is already registered") from exc
    session.refresh(user)
    return user


@router.post("/api/auth/login", response_model=AccessToken)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> AccessToken:
    user = session.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid email or password")
    try:
        return AccessToken(access_token=create_access_token(user.id))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="JWT authentication is not configured") from exc


@router.get("/api/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/api/messages", response_model=list[TuyaMessageRead])
def list_messages(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[TuyaMessage]:
    """Local development diagnostic endpoint retained from Phase 1."""

    return list(session.scalars(select(TuyaMessage).order_by(TuyaMessage.received_at.desc()).limit(limit)))


@router.get("/api/devices", response_model=list[DeviceRead])
def list_devices(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Device]:
    return list(
        session.scalars(
            select(Device)
            .join(UserDevice, UserDevice.device_id == Device.id)
            .where(UserDevice.user_id == current_user.id)
            .order_by(Device.created_at.desc())
        )
    )


@router.post("/api/devices/bind", response_model=DeviceBindRead, status_code=status.HTTP_201_CREATED)
def bind_device(
    payload: DeviceBindRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DeviceBindRead:
    device_id = payload.device_id.strip()
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device does not exist")
    binding = session.scalar(select(UserDevice).where(UserDevice.device_id == device_id))
    if binding is not None:
        message = "device is already bound to this user" if binding.user_id == current_user.id else "device is bound to another user"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    session.add(UserDevice(user_id=current_user.id, device_id=device_id))
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="device is already bound") from exc
    return DeviceBindRead(device_id=device_id, bound=True)


@router.delete("/api/devices/{device_id}/bind", status_code=status.HTTP_204_NO_CONTENT)
def unbind_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    binding = session.scalar(
        select(UserDevice).where(UserDevice.device_id == device_id, UserDevice.user_id == current_user.id)
    )
    if binding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device binding not found")
    session.delete(binding)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _owned_sessions_statement(user_id: str, device_id: str | None = None):
    statement = (
        select(TrainingSession)
        .join(UserDevice, UserDevice.device_id == TrainingSession.device_id)
        .where(UserDevice.user_id == user_id)
    )
    if device_id:
        statement = statement.where(TrainingSession.device_id == device_id)
    return statement


def _owned_training_session(session: Session, user_id: str, session_id: str) -> TrainingSession:
    record = session.scalar(_owned_sessions_statement(user_id).where(TrainingSession.id == session_id))
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="training session not found")
    return record


@router.get("/api/training-sessions", response_model=TrainingSessionPage)
def list_training_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    device_id: str | None = Query(default=None, min_length=1, max_length=128),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TrainingSessionPage:
    statement = _owned_sessions_statement(current_user.id, device_id)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = list(
        session.scalars(
            statement.order_by(TrainingSession.started_at.desc(), TrainingSession.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return TrainingSessionPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/api/training-sessions/{session_id}", response_model=TrainingSessionRead)
def get_training_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TrainingSession:
    return _owned_training_session(session, current_user.id, session_id)


def _actions(summary: Any) -> list[dict[str, Any]]:
    if not isinstance(summary, dict):
        return []
    actions = summary.get("actions")
    if not isinstance(actions, dict):
        return []
    return [
        {"name": str(name), "count": value}
        for name, value in sorted(actions.items(), key=lambda item: str(item[0]))
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]


@router.get("/api/training-sessions/{session_id}/report", response_model=TrainingReport)
def get_training_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TrainingReport:
    record = _owned_training_session(session, current_user.id, session_id)
    summary = record.summary_json if isinstance(record.summary_json, dict) else {"raw": record.summary_json}
    fault_count = summary.get("fault_count") if isinstance(summary.get("fault_count"), int) else None
    device_status = summary.get("device_status") if isinstance(summary.get("device_status"), str) else None
    return TrainingReport(
        id=record.id,
        device_id=record.device_id,
        training_time=record.started_at or record.created_at,
        duration_sec=record.duration_sec or 0,
        total_reps=record.total_reps or 0,
        avg_confidence=(record.avg_confidence or 0) / 100,
        range_of_motion={
            "elbow_max": (record.max_elbow_angle or 0) / 10,
            "shoulder_max": (record.max_shoulder_angle or 0) / 10,
        },
        actions=_actions(summary),
        device_status=device_status,
        fault_count=fault_count,
        training_type=record.training_type,
        summary_json=summary,
        notice="Training performance summary only; it is not a medical diagnosis or treatment recommendation.",
    )
