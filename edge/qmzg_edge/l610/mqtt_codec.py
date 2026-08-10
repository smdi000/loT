from __future__ import annotations

import struct


def encode_remaining_length(value: int) -> bytes:
    if not 0 <= value <= 268435455:
        raise ValueError("MQTT Remaining Length is out of range")
    encoded = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value:
            digit |= 0x80
        encoded.append(digit)
        if not value:
            return bytes(encoded)


def mqtt_utf8(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) > 65535:
        raise ValueError("MQTT UTF-8 string exceeds 65535 bytes")
    return struct.pack("!H", len(encoded)) + encoded


def build_publish_packet(topic: str, payload: bytes, packet_id: int, qos: int = 1) -> bytes:
    if qos not in {0, 1}:
        raise ValueError("edge profile supports MQTT QoS 0 or 1 only")
    if qos == 1 and not 1 <= packet_id <= 65535:
        raise ValueError("QoS 1 PUBLISH requires a non-zero packet identifier")
    variable_header = mqtt_utf8(topic)
    if qos == 1:
        variable_header += struct.pack("!H", packet_id)
    first_byte = 0x30 | (qos << 1)
    remaining = variable_header + payload
    return bytes([first_byte]) + encode_remaining_length(len(remaining)) + remaining
