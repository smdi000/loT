from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass


@dataclass(frozen=True)
class TuyaMqttCredentials:
    timestamp: int
    client_id: str
    username: str
    password: str
    sign_content: str


def build_tuya_mqtt_credentials(device_id: str, device_secret: str, timestamp: int) -> TuyaMqttCredentials:
    if timestamp <= 0:
        raise ValueError("timestamp must be a positive Unix second value")
    if not device_id or not device_secret:
        raise ValueError("device_id and device_secret are required")
    client_id = f"tuyalink_{device_id}"
    username = (
        f"{device_id}|signMethod=hmacSha256,timestamp={timestamp},"
        "secureMode=1,accessType=1"
    )
    sign_content = f"deviceId={device_id},timestamp={timestamp},secureMode=1,accessType=1"
    password = hmac.new(
        device_secret.encode("utf-8"),
        sign_content.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return TuyaMqttCredentials(timestamp, client_id, username, password, sign_content)
