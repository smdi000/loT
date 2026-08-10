"""Run the Phase 4-A real-device acceptance without persisting API credentials.

This deployment helper composes already accepted code.  It does not modify the
L610 publisher, Tuya authentication, MQTT codec, or backend business logic.
The temporary password and JWT exist only in this process and are never logged.
"""

from __future__ import annotations

import json
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
API_BASE = "http://47.250.160.90"
SESSION_ID = "acceptance_cloud_training_001"
PROBE_PATTERN = re.compile(r"STAGE 1 COMPLETE \| AT_PORT=(COM\d+) \| BAUDRATE=(\d+)")


def read_env_value(path: Path, name: str) -> str:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            result = value.strip().strip('"').strip("'")
            if result:
                return result
    raise RuntimeError(f"{name} is missing from {path.name}")


def latest_confirmed_port() -> tuple[str, int, Path]:
    logs = sorted((ROOT / "logs").glob("l610_serial_probe_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in logs:
        match = PROBE_PATTERN.search(path.read_text(encoding="utf-8", errors="replace"))
        if match:
            return match.group(1), int(match.group(2)), path
    raise RuntimeError("no successful L610 serial probe log was found")


def api(method: str, path: str, body: dict[str, Any] | None = None, token: str | None = None) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            payload = response.read()
            return json.loads(payload) if payload else None
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API {method} {path} failed with HTTP {exc.code}: {detail}") from exc


def masked(value: str) -> str:
    return f"…{value[-4:]}" if len(value) >= 4 else "…"


def find_session(token: str, timeout_seconds: int = 120) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        page = api("GET", "/api/training-sessions?page=1&page_size=100", token=token)
        for item in page.get("items", []):
            if item.get("external_session_id") == SESSION_ID:
                return item
        time.sleep(3)
    raise RuntimeError(f"{SESSION_ID} did not appear through the public history API")


def validate_business_result(item: dict[str, Any], detail: dict[str, Any], report: dict[str, Any]) -> None:
    assert item["external_session_id"] == SESSION_ID
    assert detail["external_session_id"] == SESSION_ID
    assert detail["duration_sec"] == 623
    assert detail["total_reps"] == 57
    assert detail["avg_confidence"] == 9670
    assert detail["max_elbow_angle"] == 1285
    assert detail["max_shoulder_angle"] == 934
    assert detail["source_type"] == "tuya_property"
    assert detail["user_id"]
    assert report["duration_sec"] == 623
    assert report["total_reps"] == 57
    assert report["avg_confidence"] == 96.7
    assert report["range_of_motion"] == {"elbow_max": 128.5, "shoulder_max": 93.4}
    assert report["fault_count"] == 0
    actions = {row["name"]: row["count"] for row in report["actions"]}
    assert actions == {"boxing": 10, "curl": 20, "lateral": 12, "raise": 15}
    assert "medical diagnosis" in report["notice"]


def main() -> int:
    device_id = read_env_value(ROOT / ".env", "TUYA_DEVICE_ID")
    port, baudrate, probe_log = latest_confirmed_port()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    email = f"cloud-acceptance-{stamp}@example.invalid"
    password = secrets.token_urlsafe(24)

    print(f"ACCEPTANCE START | API={API_BASE} | session_id={SESSION_ID}")
    print(f"SERIAL SOURCE | port={port} | baudrate={baudrate} | probe_log={probe_log.name}")
    print(f"DEVICE | id={masked(device_id)}")

    user = api(
        "POST",
        "/api/auth/register",
        {"email": email, "password": password, "display_name": "Cloud Acceptance"},
    )
    login = api("POST", "/api/auth/login", {"email": email, "password": password})
    token = login["access_token"]
    binding = api("POST", "/api/devices/bind", {"device_id": device_id}, token=token)
    if not binding.get("bound"):
        raise RuntimeError("device binding was not confirmed")
    print(f"USER AND DEVICE | registered=true | user_id={masked(user['id'])} | bound=true")

    sys.path.insert(0, str(ROOT))
    import l610_tuya_training_summary as publisher

    publisher.SERIAL_PORT = port
    publisher.BAUDRATE = baudrate
    publisher.TRAINING_SESSION_ID = SESSION_ID
    publish_result = publisher.main()
    if publish_result != 0:
        raise RuntimeError(f"L610 training summary publisher returned {publish_result}")
    print("DEVICE PUBLISH | mqtt_and_tuya_ack=true")

    item = find_session(token)
    session_uuid = item["id"]
    detail = api("GET", f"/api/training-sessions/{session_uuid}", token=token)
    report = api("GET", f"/api/training-sessions/{session_uuid}/report", token=token)
    validate_business_result(item, detail, report)

    print(
        "PUBLIC HISTORY | found=true | total_at_least=1 | "
        f"session_uuid={session_uuid} | user_assigned={bool(detail['user_id'])}"
    )
    print(
        "PUBLIC DETAIL | duration_sec=623 | total_reps=57 | avg_confidence=9670 | "
        "elbow=1285 | shoulder=934 | source_type=tuya_property"
    )
    print(
        "PUBLIC REPORT | duration_sec=623 | total_reps=57 | avg_confidence=96.70 | "
        "elbow_max=128.5 | shoulder_max=93.4 | actions=4 | fault_count=0"
    )
    print("ACCEPTANCE SUCCESS | credentials_persisted=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
