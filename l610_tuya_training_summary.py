"""Publish one complete Training Summary through the accepted L610 TuyaLink path.

This compatibility publisher is deliberately separate from the accepted Event
publisher.  It temporarily uses TuyaLink Property Report because the current
TuyaLink Event -> Message Service conversion is under platform investigation.
All TLS, Tuya authentication, MQTT framing, and MIPSEND helpers are reused
unchanged from the already accepted scripts.
"""

from __future__ import annotations

import json
import logging
import struct
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import serial

from l610_serial_probe import open_serial
from l610_tls_probe import (
    BAUDRATE,
    COMMAND_TIMEOUT_SECONDS,
    MIPCALL_TIMEOUT_SECONDS,
    MIPOPEN_TIMEOUT_SECONDS,
    REMOTE_HOST,
    REMOTE_PORT,
    SERIAL_PORT,
    load_official_trust_certificate,
    mipcall_dial_complete,
    mipcall_status,
    mipopen_complete,
    parse_free_socket_ids,
    parse_single_integer,
    parse_trustfile_count,
    send_and_collect,
    socket_open_succeeded,
    valid_ipv4,
)
from l610_tuya_connect import (
    SOCKET_ID,
    assert_reference_program_not_running,
    build_connect_packet,
    build_reference,
    close_socket,
    format_hex,
    parse_connack,
    send_mqtt_connect,
    validate_connect_packet,
)
from l610_tuya_publish import (
    MQTT_RESPONSE_TIMEOUT_SECONDS,
    PUBLISH_PACKET_ID,
    SUCCESS_HOLD_SECONDS,
    build_publish_packet,
    build_subscribe_packet,
    has_packet_type,
    has_puback_and_response,
    parse_business_response,
    parse_puback,
    parse_publish_packet,
    parse_suback,
    read_hold_urcs,
    send_mqtt_packet,
    split_mqtt_packets,
    validate_subscribe_packet,
)


TRAINING_SESSION_ID = "acceptance_real_training_001"
DURATION_SEC = 623
TOTAL_REPS = 57
AVG_CONFIDENCE = 9670
MAX_ELBOW_ANGLE = 1285
MAX_SHOULDER_ANGLE = 934
SUMMARY_JSON = {
    "actions": {"curl": 20, "raise": 15, "lateral": 12, "boxing": 10},
    "fault_count": 0,
}


def configure_logging() -> tuple[logging.Logger, Path]:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"l610_tuya_training_summary_{stamp}.log"
    logger = logging.getLogger("l610-tuya-training-summary")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger, log_path


def build_training_summary_json() -> tuple[str, int, int, int, bytes, dict[str, object]]:
    """Build exactly one compact, self-contained TuyaLink Property Report."""

    ended_at = int(time.time() * 1000)
    started_at = ended_at - DURATION_SEC * 1000
    msg_id = "l610ts" + uuid.uuid4().hex[:26]
    compact_summary = json.dumps(SUMMARY_JSON, ensure_ascii=False, separators=(",", ":"))
    payload: dict[str, object] = {
        "msgId": msg_id,
        "time": ended_at,
        "sys": {"ack": 1},
        "data": {
            "training_session_id": {"value": TRAINING_SESSION_ID, "time": ended_at},
            "training_started_at": {"value": started_at, "time": ended_at},
            "training_ended_at": {"value": ended_at, "time": ended_at},
            "training_duration_sec": {"value": DURATION_SEC, "time": ended_at},
            "training_total_reps": {"value": TOTAL_REPS, "time": ended_at},
            "training_avg_confidence": {"value": AVG_CONFIDENCE, "time": ended_at},
            "training_max_elbow_angle": {"value": MAX_ELBOW_ANGLE, "time": ended_at},
            # Tuya Thing Model boundary identifier; business code maps it to max_shoulder_angle.
            "training_max_shldr_angle": {"value": MAX_SHOULDER_ANGLE, "time": ended_at},
            "training_summary_json": {"value": compact_summary, "time": ended_at},
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(msg_id) > 32:
        raise AssertionError("msgId exceeds 32 characters")
    if len(compact_summary.encode("utf-8")) > 255:
        raise AssertionError("training_summary_json exceeds its Thing Model limit")
    return msg_id, started_at, ended_at, ended_at, encoded, payload


def validate_training_summary_publish(
    packet: bytes, expected_topic: str, expected_msg_id: str
) -> dict[str, object]:
    """Parse the locally-built MQTT packet before it is ever sent to L610."""

    parsed = parse_publish_packet(packet)
    assert packet[0] == 0x32
    assert parsed.qos == 1
    assert not parsed.retain and not parsed.dup
    assert parsed.topic == expected_topic
    assert parsed.packet_identifier == PUBLISH_PACKET_ID
    decoded = json.loads(parsed.payload.decode("utf-8"))
    assert decoded["msgId"] == expected_msg_id
    assert decoded["sys"] == {"ack": 1}
    data = decoded["data"]
    assert data["training_session_id"]["value"] == TRAINING_SESSION_ID
    assert data["training_duration_sec"]["value"] == DURATION_SEC
    assert data["training_total_reps"]["value"] == TOTAL_REPS
    assert data["training_avg_confidence"]["value"] == AVG_CONFIDENCE
    assert data["training_max_elbow_angle"]["value"] == MAX_ELBOW_ANGLE
    assert data["training_max_shldr_angle"]["value"] == MAX_SHOULDER_ANGLE
    assert json.loads(data["training_summary_json"]["value"]) == SUMMARY_JSON
    return decoded


def main() -> int:
    logger, log_path = configure_logging()
    mqtt_connected = False
    suback = b""
    puback = b""
    response_code: int | None = None
    socket_closed = False
    msg_id = ""
    publish_packet = b""
    json_bytes = b""
    mipsend_actual = 0

    logger.info("L610 TRAINING SUMMARY START | port=%s | baudrate=%d | log=%s", SERIAL_PORT, BAUDRATE, log_path)
    logger.info("BOUNDARY | one complete property report | one publish only | no Event model changes")
    try:
        assert_reference_program_not_running(logger)
        reference = build_reference()
        connect_packet, _ = build_connect_packet(reference)
        validate_connect_packet(connect_packet, reference)
        device_id = reference.client_id.removeprefix("tuyalink_")
        response_topic = f"tylink/{device_id}/thing/property/report_response"
        publish_topic = f"tylink/{device_id}/thing/property/report"

        subscribe_packet, subscribe_remaining = build_subscribe_packet(response_topic)
        parsed_subscribe = validate_subscribe_packet(subscribe_packet, response_topic)
        logger.info(
            "SUBSCRIBE PRECHECK | topic=%s | packet_id=%d | qos=%d | remaining=%d | total=%d",
            parsed_subscribe.topic, parsed_subscribe.packet_identifier, parsed_subscribe.requested_qos,
            subscribe_remaining, len(subscribe_packet),
        )

        msg_id, started_at, ended_at, timestamp_ms, json_bytes, payload = build_training_summary_json()
        publish_packet, publish_remaining = build_publish_packet(publish_topic, json_bytes)
        decoded = validate_training_summary_publish(publish_packet, publish_topic, msg_id)
        parsed_publish = parse_publish_packet(publish_packet)
        if parsed_publish.remaining_length != publish_remaining:
            raise AssertionError("PUBLISH builder/parser Remaining Length mismatch")
        logger.info("SUMMARY PRECHECK | session_id=%s | started_at=%d | ended_at=%d", TRAINING_SESSION_ID, started_at, ended_at)
        logger.info("SUMMARY PRECHECK | JSON=%s", json.dumps(decoded, ensure_ascii=False, separators=(",", ":")))
        logger.info("SUMMARY PRECHECK | JSON UTF-8 length=%d | mqtt_total=%d | remaining=%d", len(json_bytes), len(publish_packet), publish_remaining)
        logger.info("PUBLISH HEX BEGIN\n%s\nPUBLISH HEX END", format_hex(publish_packet))

        with open_serial(SERIAL_PORT, BAUDRATE, COMMAND_TIMEOUT_SECONDS) as connection:
            time.sleep(0.20)
            at_result = send_and_collect(connection, logger, "AT")
            if not at_result.ok:
                raise RuntimeError("AT did not return OK")
            mipcall_query = send_and_collect(connection, logger, "AT+MIPCALL?")
            status = mipcall_status(mipcall_query.raw)
            local_ip = valid_ipv4(mipcall_query.raw)
            if status == 0:
                dial_result = send_and_collect(connection, logger, "AT+MIPCALL=1", timeout=MIPCALL_TIMEOUT_SECONDS, completion=mipcall_dial_complete, quiet_period=0.50)
                if dial_result.error:
                    raise RuntimeError("AT+MIPCALL=1 returned ERROR")
                mipcall_query = send_and_collect(connection, logger, "AT+MIPCALL?")
                status = mipcall_status(mipcall_query.raw)
                local_ip = valid_ipv4(mipcall_query.raw) or valid_ipv4(dial_result.raw)
            if status != 1 or not local_ip:
                raise RuntimeError("L610 has no active IPv4 MIPCALL")
            logger.info("MIPCALL CONFIRMED | status=1 | ipv4=%s", local_ip)

            version = send_and_collect(connection, logger, "AT+GTSSLVER?")
            mode = send_and_collect(connection, logger, "AT+GTSSLMODE?")
            files = send_and_collect(connection, logger, "AT+GTSSLFILE?")
            if parse_single_integer(version.raw, b"+GTSSLVER:") != 4 or parse_single_integer(mode.raw, b"+GTSSLMODE:") != 1:
                raise RuntimeError("TLS is not restored; run l610_tls_restore.py before this summary test")
            trust_count = parse_trustfile_count(files.raw)
            if trust_count == 0:
                certificate = load_official_trust_certificate(connection, logger)
                if not certificate.ok:
                    raise RuntimeError("could not restore Tuya TRUSTFILE")
                files = send_and_collect(connection, logger, "AT+GTSSLFILE?")
                trust_count = parse_trustfile_count(files.raw)
            if trust_count is None or trust_count < 1:
                raise RuntimeError("no TRUSTFILE is available")

            receive_format = send_and_collect(connection, logger, 'AT+GTSET="IPRFMT",0')
            if not receive_format.ok:
                raise RuntimeError("could not set IPRFMT=0")
            free_ids = parse_free_socket_ids(send_and_collect(connection, logger, "AT+MIPOPEN?").raw)
            if free_ids is None or SOCKET_ID not in free_ids:
                raise RuntimeError("socket 1 is not free")
            opened = send_and_collect(connection, logger, f'AT+MIPOPEN={SOCKET_ID},,"{REMOTE_HOST}",{REMOTE_PORT},2', timeout=MIPOPEN_TIMEOUT_SECONDS, completion=mipopen_complete(SOCKET_ID), quiet_period=0.75)
            if not socket_open_succeeded(opened.raw, SOCKET_ID):
                raise RuntimeError("TLS socket did not receive +MIPOPEN: 1,1")

            try:
                connected = send_mqtt_connect(connection, logger, SOCKET_ID, connect_packet)
                if not connected.send_status_ok:
                    raise RuntimeError("MQTT CONNECT MIPSEND failed")
                connack, connack_code = parse_connack(connected.received_socket_bytes)
                logger.info("CONNACK HEX | %s", connack.hex(" ").upper())
                if connack_code != 0:
                    raise RuntimeError(f"MQTT CONNACK return code is {connack_code}")
                mqtt_connected = True
                logger.info("MQTT CONNECT SUCCESS")

                subscribed = send_mqtt_packet(connection, logger, SOCKET_ID, subscribe_packet, lambda data: has_packet_type(data, 9))
                if not subscribed.send_status_ok:
                    raise RuntimeError("SUBSCRIBE MIPSEND failed")
                subscribe_packets, remainder = split_mqtt_packets(subscribed.received_socket_bytes)
                if remainder:
                    raise RuntimeError("incomplete MQTT bytes remained after SUBACK wait")
                suback, granted_qos = parse_suback(subscribe_packets)
                logger.info("SUBACK SUCCESS | hex=%s | granted_qos=%d", suback.hex(" ").upper(), granted_qos)

                published = send_mqtt_packet(connection, logger, SOCKET_ID, publish_packet, lambda data: has_puback_and_response(data, response_topic), timeout=MQTT_RESPONSE_TIMEOUT_SECONDS)
                mipsend_actual = len(published.socket_payload)
                if not published.send_status_ok:
                    raise RuntimeError("PUBLISH MIPSEND failed")
                publish_packets, remainder = split_mqtt_packets(published.received_socket_bytes)
                if remainder:
                    raise RuntimeError("incomplete MQTT bytes remained after property response wait")
                puback = parse_puback(publish_packets)
                logger.info("PUBACK SUCCESS | hex=%s", puback.hex(" ").upper())
                _, inbound, response = parse_business_response(publish_packets, response_topic, msg_id)
                response_code = int(response["code"])
                logger.info("TUYA RESPONSE TOPIC | %s", inbound.topic)
                logger.info("TUYA RESPONSE JSON | %s", json.dumps(response, ensure_ascii=False, separators=(",", ":")))
                logger.info("TUYA BUSINESS ACK SUCCESS | code=%d", response_code)
                if inbound.qos == 1 and inbound.packet_identifier is not None:
                    inbound_puback = b"\x40\x02" + struct.pack("!H", inbound.packet_identifier)
                    acknowledgement = send_mqtt_packet(connection, logger, SOCKET_ID, inbound_puback, None, timeout=5.0)
                    if not acknowledgement.send_status_ok:
                        raise RuntimeError("could not PUBACK inbound Tuya response")
                read_hold_urcs(connection, logger, SUCCESS_HOLD_SECONDS)
            finally:
                socket_closed = close_socket(connection, logger, SOCKET_ID)

        complete = mqtt_connected and bool(suback) and bool(puback) and response_code == 0 and socket_closed
        logger.info("TRAINING SUMMARY DEVICE RESULT | complete=%s", complete)
        return 0 if complete else 8
    except (AssertionError, RuntimeError, ValueError, KeyError, TypeError, serial.SerialException, OSError) as exc:
        logger.error("TRAINING SUMMARY STOP | %s", exc)
        return 9
    finally:
        logger.info(
            "FINAL EVIDENCE | session_id=%s | mqtt_connect=%s | suback=%s | json_bytes=%s | publish_total=%s | mipsend_actual=%s | puback=%s | code=%s | socket_closed=%s",
            TRAINING_SESSION_ID, mqtt_connected, suback.hex(" ").upper() if suback else "none",
            len(json_bytes) if json_bytes else "none", len(publish_packet) if publish_packet else "none",
            mipsend_actual or "none", puback.hex(" ").upper() if puback else "none",
            response_code if response_code is not None else "none", socket_closed,
        )
        logger.info("LOG PATH | %s", log_path)


if __name__ == "__main__":
    raise SystemExit(main())
