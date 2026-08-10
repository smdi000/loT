"""Report one TuyaLink ``training_completed`` event through the accepted L610 path.

This script intentionally reuses the already accepted serial, MIPCALL, TLS,
Tuya authentication, MQTT CONNECT, MQTT codec, and binary MIPSEND helpers.  It
adds only the TuyaLink Event JSON and event response validation.
"""

from __future__ import annotations

import argparse
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
    PUBLISH_PACKET_ID,
    SUBSCRIBE_PACKET_ID,
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


EVENT_CODE = "training_completed"
DURATION_SEC = 623
TOTAL_REPS = 57
AVG_CONFIDENCE = 9670
MAX_ELBOW_ANGLE = 1284
MAX_SHOULDER_ANGLE = 1148
SUMMARY = {
    "actions": {
        "curl": 20,
        "raise": 15,
        "lateral": 12,
        "boxing": 10,
    },
    "fault_count": 0,
}


def configure_logging() -> tuple[logging.Logger, Path]:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"l610_tuya_training_event_{stamp}.log"

    logger = logging.getLogger("l610-tuya-training-event")
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


def build_event_json(session_id: str) -> tuple[str, int, bytes, dict[str, object]]:
    if len(session_id.encode("utf-8")) > 64:
        raise ValueError("session_id exceeds the Thing Model limit of 64 bytes")

    ended_at = int(time.time() * 1000)
    started_at = ended_at - DURATION_SEC * 1000
    msg_id = "l610evt" + uuid.uuid4().hex[:25]
    summary_json = json.dumps(SUMMARY, ensure_ascii=False, separators=(",", ":"))
    if len(msg_id) > 32:
        raise AssertionError("msgId exceeds 32 characters")
    if len(summary_json.encode("utf-8")) > 255:
        raise AssertionError("summary_json exceeds the Thing Model limit of 255 bytes")

    payload: dict[str, object] = {
        "msgId": msg_id,
        "time": ended_at,
        "sys": {"ack": 1},
        "data": {
            "eventCode": EVENT_CODE,
            "eventTime": ended_at,
            "outputParams": {
                "session_id": session_id,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_sec": DURATION_SEC,
                "total_reps": TOTAL_REPS,
                "avg_confidence": AVG_CONFIDENCE,
                "max_elbow_angle": MAX_ELBOW_ANGLE,
                "max_shoulder_angle": MAX_SHOULDER_ANGLE,
                "summary_json": summary_json,
            },
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return msg_id, ended_at, encoded, payload


def validate_event_publish(
    packet: bytes,
    expected_topic: str,
    expected_msg_id: str,
    expected_session_id: str,
) -> tuple[object, dict[str, object]]:
    parsed = parse_publish_packet(packet)
    assert packet[0] == 0x32
    assert parsed.qos == 1
    assert not parsed.retain
    assert not parsed.dup
    assert parsed.topic == expected_topic
    assert parsed.packet_identifier == PUBLISH_PACKET_ID

    decoded = json.loads(parsed.payload.decode("utf-8"))
    output = decoded["data"]["outputParams"]
    assert decoded["msgId"] == expected_msg_id
    assert decoded["sys"]["ack"] == 1
    assert decoded["data"]["eventCode"] == EVENT_CODE
    assert decoded["data"]["eventTime"] == decoded["time"]
    assert output["session_id"] == expected_session_id
    assert output["ended_at"] - output["started_at"] == DURATION_SEC * 1000
    assert output["duration_sec"] == DURATION_SEC
    assert output["total_reps"] == TOTAL_REPS
    assert output["avg_confidence"] == AVG_CONFIDENCE
    assert output["max_elbow_angle"] == MAX_ELBOW_ANGLE
    assert output["max_shoulder_angle"] == MAX_SHOULDER_ANGLE
    assert json.loads(output["summary_json"]) == SUMMARY
    return parsed, decoded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send one training_completed event through the L610 TLS socket."
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Training session ID (UTF-8 length <= 64 bytes). Default: a unique test ID.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session_id = args.session_id or (
        "test_" + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    )
    logger, log_path = configure_logging()

    mqtt_connected = False
    suback = b""
    puback = b""
    response_code: int | None = None
    response_json: dict[str, object] | None = None
    response_topic = ""
    socket_closed = False
    event_exchange = None
    event_packet = b""
    event_json = b""
    msg_id = ""

    logger.info(
        "L610 TUYA TRAINING EVENT START | port=%s | baudrate=%d | host=%s | "
        "remote_port=%d | log=%s",
        SERIAL_PORT,
        BAUDRATE,
        REMOTE_HOST,
        REMOTE_PORT,
        log_path,
    )
    logger.info("BOUNDARY | one training_completed event | no property report | no control")

    try:
        assert_reference_program_not_running(logger)
        reference = build_reference()
        connect_packet, _ = build_connect_packet(reference)
        validate_connect_packet(connect_packet, reference)

        device_id = reference.client_id.removeprefix("tuyalink_")
        subscribe_topic = f"tylink/{device_id}/thing/event/trigger_response"
        publish_topic = f"tylink/{device_id}/thing/event/trigger"

        subscribe_packet, subscribe_remaining = build_subscribe_packet(subscribe_topic)
        parsed_subscribe = validate_subscribe_packet(subscribe_packet, subscribe_topic)
        logger.info(
            "SUBSCRIBE SELF-CHECK | topic=%s | packet_id=%d | qos=%d | "
            "remaining_length=%d | total=%d",
            parsed_subscribe.topic,
            parsed_subscribe.packet_identifier,
            parsed_subscribe.requested_qos,
            subscribe_remaining,
            len(subscribe_packet),
        )
        logger.info("SUBSCRIBE HEX BEGIN\n%s\nSUBSCRIBE HEX END", format_hex(subscribe_packet))

        msg_id, timestamp_ms, event_json, event_payload = build_event_json(session_id)
        event_packet, publish_remaining = build_publish_packet(publish_topic, event_json)
        parsed_event, decoded_event = validate_event_publish(
            event_packet,
            publish_topic,
            msg_id,
            session_id,
        )
        logger.info("EVENT PRECHECK | topic=%s", publish_topic)
        logger.info("EVENT PRECHECK | response_topic=%s", subscribe_topic)
        logger.info("EVENT PRECHECK | eventCode=%s | session_id=%s", EVENT_CODE, session_id)
        logger.info("EVENT PRECHECK | msgId=%s | timestamp=%d", msg_id, timestamp_ms)
        logger.info(
            "EVENT PRECHECK | JSON=%s",
            json.dumps(decoded_event, ensure_ascii=False, separators=(",", ":")),
        )
        logger.info(
            "EVENT PRECHECK | JSON UTF-8=%d | total=%d | remaining_length=%d | "
            "packet_identifier=%d",
            len(event_json),
            len(event_packet),
            parsed_event.remaining_length,
            parsed_event.packet_identifier,
        )
        if publish_remaining != parsed_event.remaining_length:
            raise AssertionError("Event PUBLISH Remaining Length mismatch")
        logger.info("EVENT PUBLISH HEX BEGIN\n%s\nEVENT PUBLISH HEX END", format_hex(event_packet))
        logger.info(
            "EVENT SELF-CHECK | qos=1 | sys_ack=1 | event_code_match=true | "
            "session_id_match=true | value_checks=true"
        )

        with open_serial(SERIAL_PORT, BAUDRATE, COMMAND_TIMEOUT_SECONDS) as connection:
            time.sleep(0.20)
            if not send_and_collect(connection, logger, "AT").ok:
                raise RuntimeError(f"{SERIAL_PORT} did not return OK for AT")

            mipcall_query = send_and_collect(connection, logger, "AT+MIPCALL?")
            status = mipcall_status(mipcall_query.raw)
            local_ip = valid_ipv4(mipcall_query.raw)
            if status == 0:
                dial_result = send_and_collect(
                    connection,
                    logger,
                    "AT+MIPCALL=1",
                    timeout=MIPCALL_TIMEOUT_SECONDS,
                    completion=mipcall_dial_complete,
                    quiet_period=0.50,
                )
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
            if parse_single_integer(version.raw, b"+GTSSLVER:") != 4:
                raise RuntimeError("TLS version is not TLS 1.2")
            if parse_single_integer(mode.raw, b"+GTSSLMODE:") != 1:
                raise RuntimeError("server certificate verification is disabled")
            trust_count = parse_trustfile_count(files.raw)
            if trust_count == 0:
                certificate = load_official_trust_certificate(connection, logger)
                if not certificate.ok:
                    raise RuntimeError("could not restore Tuya TRUSTFILE")
                files = send_and_collect(connection, logger, "AT+GTSSLFILE?")
                trust_count = parse_trustfile_count(files.raw)
            if trust_count is None or trust_count < 1:
                raise RuntimeError("no TRUSTFILE is available")

            if not send_and_collect(connection, logger, 'AT+GTSET="IPRFMT",0').ok:
                raise RuntimeError("could not set IPRFMT=0")
            free_query = send_and_collect(connection, logger, "AT+MIPOPEN?")
            free_ids = parse_free_socket_ids(free_query.raw)
            if free_ids is None or SOCKET_ID not in free_ids:
                raise RuntimeError(f"socket {SOCKET_ID} is not free")

            open_result = send_and_collect(
                connection,
                logger,
                f'AT+MIPOPEN={SOCKET_ID},,"{REMOTE_HOST}",{REMOTE_PORT},2',
                timeout=MIPOPEN_TIMEOUT_SECONDS,
                completion=mipopen_complete(SOCKET_ID),
                quiet_period=0.75,
            )
            if not socket_open_succeeded(open_result.raw, SOCKET_ID):
                raise RuntimeError("TLS socket did not receive +MIPOPEN: 1,1")

            try:
                connect_exchange = send_mqtt_connect(
                    connection,
                    logger,
                    SOCKET_ID,
                    connect_packet,
                )
                if not connect_exchange.send_status_ok:
                    raise RuntimeError("MQTT CONNECT MIPSEND failed")
                connack, connack_code = parse_connack(connect_exchange.received_socket_bytes)
                logger.info("CONNACK HEX | %s", connack.hex(" ").upper())
                if connack_code != 0:
                    raise RuntimeError(f"MQTT CONNACK return code is {connack_code}")
                mqtt_connected = True
                logger.info("MQTT CONNECT SUCCESS")

                subscribe_exchange = send_mqtt_packet(
                    connection,
                    logger,
                    SOCKET_ID,
                    subscribe_packet,
                    lambda data: has_packet_type(data, 9),
                )
                if not subscribe_exchange.send_status_ok:
                    raise RuntimeError("Event response SUBSCRIBE MIPSEND failed")
                subscribe_packets, subscribe_remainder = split_mqtt_packets(
                    subscribe_exchange.received_socket_bytes
                )
                if subscribe_remainder:
                    raise RuntimeError("incomplete MQTT bytes remained after SUBACK")
                suback, granted_qos = parse_suback(subscribe_packets)
                logger.info(
                    "SUBACK SUCCESS | hex=%s | packet_id=%d | granted_qos=%d",
                    suback.hex(" ").upper(),
                    SUBSCRIBE_PACKET_ID,
                    granted_qos,
                )

                event_exchange = send_mqtt_packet(
                    connection,
                    logger,
                    SOCKET_ID,
                    event_packet,
                    lambda data: has_puback_and_response(data, subscribe_topic),
                )
                if not event_exchange.send_status_ok:
                    raise RuntimeError("Event PUBLISH MIPSEND failed")
                event_packets, event_remainder = split_mqtt_packets(
                    event_exchange.received_socket_bytes
                )
                if event_remainder:
                    raise RuntimeError("incomplete MQTT bytes remained after Event response")
                puback = parse_puback(event_packets)
                logger.info("PUBACK SUCCESS | hex=%s", puback.hex(" ").upper())

                _, inbound_publish, response_json = parse_business_response(
                    event_packets,
                    subscribe_topic,
                    msg_id,
                )
                response_topic = inbound_publish.topic
                response_code = int(response_json["code"])
                logger.info("TUYA EVENT RESPONSE TOPIC | %s", response_topic)
                logger.info(
                    "TUYA EVENT RESPONSE JSON | %s",
                    json.dumps(response_json, ensure_ascii=False, separators=(",", ":")),
                )
                logger.info("TUYA EVENT ACK SUCCESS | code=%d", response_code)

                if inbound_publish.qos == 1:
                    if inbound_publish.packet_identifier is None:
                        raise RuntimeError("inbound Event response lacks packet identifier")
                    inbound_puback = b"\x40\x02" + struct.pack(
                        "!H", inbound_publish.packet_identifier
                    )
                    acknowledgement = send_mqtt_packet(
                        connection,
                        logger,
                        SOCKET_ID,
                        inbound_puback,
                        response_complete=None,
                        timeout=5.0,
                    )
                    if not acknowledgement.send_status_ok:
                        raise RuntimeError("could not PUBACK the inbound Tuya Event response")
                    logger.info(
                        "INBOUND EVENT RESPONSE PUBACK SENT | packet_id=%d | hex=%s",
                        inbound_publish.packet_identifier,
                        inbound_puback.hex(" ").upper(),
                    )

                read_hold_urcs(connection, logger, SUCCESS_HOLD_SECONDS)
            finally:
                socket_closed = close_socket(connection, logger, SOCKET_ID)

        complete = (
            mqtt_connected
            and bool(suback)
            and bool(puback)
            and response_code == 0
            and socket_closed
        )
        logger.info("TRAINING EVENT DEVICE-SIDE RESULT | complete=%s", complete)
        return 0 if complete else 8
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        serial.SerialException,
        OSError,
    ) as exc:
        logger.error("TRAINING EVENT STOP | %s", exc)
        return 9
    finally:
        logger.info(
            "FINAL EVIDENCE | mqtt_connect=%s | event_code=%s | session_id=%s | "
            "msgId=%s | json_bytes=%s | publish_total=%s | mipsend_actual=%s | "
            "suback=%s | puback=%s | response_topic=%s | response_json=%s | "
            "code=%s | socket_closed=%s",
            mqtt_connected,
            EVENT_CODE,
            session_id,
            msg_id or "none",
            len(event_json) if event_json else "none",
            len(event_packet) if event_packet else "none",
            len(event_exchange.socket_payload) if event_exchange else "none",
            suback.hex(" ").upper() if suback else "none",
            puback.hex(" ").upper() if puback else "none",
            response_topic or "none",
            json.dumps(response_json, ensure_ascii=False, separators=(",", ":"))
            if response_json is not None
            else "none",
            response_code if response_code is not None else "none",
            socket_closed,
        )
        logger.info("LOG PATH | %s", log_path)


if __name__ == "__main__":
    raise SystemExit(main())
