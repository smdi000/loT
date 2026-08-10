from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_string(*values: Any) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value)
    return None


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        numeric = float(value)
        if numeric > 10_000_000_000:  # Tuya message timestamps are commonly milliseconds.
            numeric /= 1000
        return datetime.fromtimestamp(numeric, tz=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _canonical_hash(raw: dict[str, Any]) -> str:
    encoded = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _property_values(*containers: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for container in containers:
        for key in ("properties", "status"):
            entries = container.get(key)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                code = entry.get("code")
                if code is not None and "value" in entry:
                    values[str(code)] = entry["value"]
    return values


@dataclass(frozen=True)
class NormalizedTuyaMessage:
    """Tuya envelope converted into stable business-facing fields."""

    biz_code: str
    tuya_msg_id: str | None
    dedup_key: str
    device_id: str | None
    product_id: str | None
    event_time: datetime | None
    payload: dict[str, Any]
    raw: dict[str, Any]
    properties: dict[str, Any]
    event_code: str | None
    output_params: dict[str, Any]


def normalize_tuya_message(raw_message: dict[str, Any]) -> NormalizedTuyaMessage:
    """Handle common Tuya Message Service envelope variants without discarding raw data."""

    raw = dict(raw_message)
    # Tuya's official Pulsar SDK decrypts Message Service data, but delivery
    # envelopes vary between service versions.
    # The real property-message shape is payload.data.bizData, whereas fixtures
    # and alternate delivery paths can expose data directly.  Preserve ``raw``
    # unchanged and normalize both shapes for the business layer.
    sdk_payload = _mapping(raw.get("payload"))
    payload = _mapping(sdk_payload.get("data")) or _mapping(raw.get("data"))
    biz_data = _mapping(payload.get("bizData")) or _mapping(raw.get("bizData"))
    biz_code = _first_string(raw.get("bizCode"), raw.get("biz_code"), payload.get("bizCode")) or "unknown"
    device_id = _first_string(
        raw.get("devId"),
        raw.get("deviceId"),
        payload.get("devId"),
        payload.get("deviceId"),
        biz_data.get("devId"),
        biz_data.get("deviceId"),
    )
    product_id = _first_string(
        raw.get("productId"),
        raw.get("productKey"),
        payload.get("productId"),
        payload.get("productKey"),
        biz_data.get("productId"),
        biz_data.get("productKey"),
    )
    tuya_msg_id = _first_string(
        raw.get("dataId"),
        raw.get("msgId"),
        raw.get("id"),
        payload.get("dataId"),
        payload.get("msgId"),
        biz_data.get("dataId"),
        biz_data.get("msgId"),
    )
    event_time = _to_datetime(
        raw.get("eventTime")
        or raw.get("time")
        or raw.get("t")
        or raw.get("ts")
        or payload.get("eventTime")
        or payload.get("time")
        or payload.get("ts")
        or biz_data.get("eventTime")
        or biz_data.get("time")
    )
    event_code = _first_string(raw.get("eventCode"), payload.get("eventCode"), biz_data.get("eventCode"))
    output_params = (
        _mapping(raw.get("outputParams"))
        or _mapping(payload.get("outputParams"))
        or _mapping(biz_data.get("outputParams"))
    )
    return NormalizedTuyaMessage(
        biz_code=biz_code,
        tuya_msg_id=tuya_msg_id,
        dedup_key=tuya_msg_id or _canonical_hash(raw),
        device_id=device_id,
        product_id=product_id,
        event_time=event_time,
        payload=payload or raw,
        raw=raw,
        properties=_property_values(raw, payload, biz_data),
        event_code=event_code,
        output_params=output_params,
    )
