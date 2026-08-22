from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models import Device, TrainingSession, UserDevice
from app.services.training import NormalizedTrainingSummary, TrainingType, create_training_session


@dataclass(frozen=True)
class DemoSession:
    session_id: str
    started_at: str
    duration_sec: int
    total_reps: int
    avg_confidence: int
    max_elbow_angle: int
    max_shoulder_angle: int
    training_type: TrainingType
    actions: dict[str, int]
    fault_count: int = 0


DEMO_SESSIONS = (
    DemoSession("demo_20260805_active_001", "2026-08-05T09:18:00+08:00", 548, 52, 9540, 1268, 918, "active_assist", {"curl": 18, "raise": 14, "lateral": 11, "boxing": 9}),
    DemoSession("demo_20260806_resistance_001", "2026-08-06T15:06:00+08:00", 782, 44, 9380, 1322, 884, "resistance", {"curl": 16, "raise": 11, "lateral": 10, "boxing": 7}),
    DemoSession("demo_20260807_passive_001", "2026-08-07T10:42:00+08:00", 631, 50, 9620, 1185, 827, "passive_assist", {"curl": 17, "raise": 14, "lateral": 11, "boxing": 8}),
    DemoSession("demo_20260809_active_001", "2026-08-09T08:55:00+08:00", 496, 47, 9710, 1294, 946, "active_assist", {"curl": 16, "raise": 13, "lateral": 10, "boxing": 8}),
    DemoSession("demo_20260810_resistance_001", "2026-08-10T16:20:00+08:00", 901, 55, 9460, 1367, 1012, "resistance", {"curl": 20, "raise": 14, "lateral": 12, "boxing": 9}),
    DemoSession("demo_20260811_active_001", "2026-08-11T11:13:00+08:00", 657, 61, 9780, 1341, 987, "active_assist", {"curl": 21, "raise": 17, "lateral": 13, "boxing": 10}),
    DemoSession("demo_20260812_passive_001", "2026-08-12T14:37:00+08:00", 720, 58, 9550, 1219, 856, "passive_assist", {"curl": 20, "raise": 16, "lateral": 13, "boxing": 9}),
    DemoSession("demo_20260814_resistance_001", "2026-08-14T09:46:00+08:00", 1008, 63, 9320, 1412, 1075, "resistance", {"curl": 23, "raise": 16, "lateral": 14, "boxing": 10}, 1),
    DemoSession("demo_20260815_active_001", "2026-08-15T17:08:00+08:00", 583, 56, 9840, 1378, 1034, "active_assist", {"curl": 19, "raise": 16, "lateral": 12, "boxing": 9}),
    DemoSession("demo_20260816_passive_001", "2026-08-16T10:25:00+08:00", 845, 66, 9610, 1247, 902, "passive_assist", {"curl": 23, "raise": 18, "lateral": 14, "boxing": 11}),
    DemoSession("demo_20260818_resistance_001", "2026-08-18T15:52:00+08:00", 934, 59, 9490, 1435, 1102, "resistance", {"curl": 22, "raise": 15, "lateral": 13, "boxing": 9}),
    DemoSession("demo_20260819_active_001", "2026-08-19T08:38:00+08:00", 512, 49, 9880, 1316, 968, "active_assist", {"curl": 17, "raise": 14, "lateral": 10, "boxing": 8}),
    DemoSession("demo_20260820_passive_001", "2026-08-20T13:19:00+08:00", 768, 62, 9670, 1276, 925, "passive_assist", {"curl": 21, "raise": 18, "lateral": 13, "boxing": 10}),
    DemoSession("demo_20260821_resistance_001", "2026-08-21T16:44:00+08:00", 1062, 68, 9440, 1441, 1128, "resistance", {"curl": 25, "raise": 18, "lateral": 14, "boxing": 11}, 1),
)


def _masked(value: str) -> str:
    return value if len(value) <= 8 else f"{value[:4]}...{value[-4:]}"


def seed_competition_history(session: Session, device_id: str, *, apply: bool = False) -> tuple[int, int]:
    device = session.get(Device, device_id)
    if device is None:
        raise ValueError("device does not exist")
    bindings = list(session.scalars(select(UserDevice).where(UserDevice.device_id == device_id)))
    if len(bindings) != 1:
        raise ValueError("device owner could not be uniquely resolved")

    existing = set(
        session.scalars(
            select(TrainingSession.external_session_id).where(
                TrainingSession.device_id == device_id,
                TrainingSession.external_session_id.in_([item.session_id for item in DEMO_SESSIONS]),
            )
        )
    )
    pending = [item for item in DEMO_SESSIONS if item.session_id not in existing]
    print(f"Would create: {len(pending)}")
    print(f"Would skip: {len(existing)}")
    print(f"Device: {_masked(device_id)}")
    print("Owner resolved: yes")
    if not apply:
        return len(pending), len(existing)

    created = 0
    for item in pending:
        started_at = datetime.fromisoformat(item.started_at)
        result = create_training_session(
            session,
            NormalizedTrainingSummary(
                external_session_id=item.session_id,
                device_id=device_id,
                started_at=started_at,
                ended_at=started_at + timedelta(seconds=item.duration_sec),
                duration_sec=item.duration_sec,
                total_reps=item.total_reps,
                avg_confidence=item.avg_confidence,
                max_elbow_angle=item.max_elbow_angle,
                max_shoulder_angle=item.max_shoulder_angle,
                summary_json={
                    "training_type": item.training_type,
                    "actions": item.actions,
                    "fault_count": item.fault_count,
                },
                source_type="mock",
                training_type=item.training_type,
            ),
        )
        created += int(result.created)
    print(f"Created: {created}")
    return created, len(existing)


def main() -> int:
    parser = argparse.ArgumentParser(description="Idempotently seed competition demo training history")
    parser.add_argument("--device-id", required=True, help="Exact existing Tuya device ID")
    parser.add_argument("--apply", action="store_true", help="Commit inserts; default is a dry-run")
    args = parser.parse_args()
    with get_session_factory()() as session:
        seed_competition_history(session, args.device_id, apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
