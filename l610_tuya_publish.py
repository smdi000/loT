"""Complete one TuyaLink property-report cycle through an L610 TLS socket.

The accepted phase-4 implementation supplies process checks, Tuya credentials,
MQTT CONNECT framing, binary MIPSEND, and CONNACK parsing. This stage adds one
SUBSCRIBE and one QoS-1 PUBLISH, then waits for both PUBACK and Tuya code=0.
"""

from __future__ import annotations

import json
import logging
import re
import struct
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import serial

from l610_serial_probe import log_serial_data, open_serial, response_lines
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
    terminal_error,
    valid_ipv4,
)
from l610_tuya_connect import (
    SOCKET_ID,
    assert_reference_program_not_running,
    build_connect_packet,
    build_reference,
    close_socket,
    decode_remaining_length,
    encode_remaining_length,
    format_hex,
    mqtt_utf8,
    parse_connack,
    send_mqtt_connect,
    validate_connect_packet,
)


SUBSCRIBE_PACKET_ID = 1
PUBLISH_PACKET_ID = 2
ACTION_CONFIDENCE = 9982
MQTT_RESPONSE_TIMEOUT_SECONDS = 30.0
SUCCESS_HOLD_SECONDS = 5.0


@dataclass(frozen=True)
class ParsedSubscribe:
    remaining_length: int
    packet_identifier: int
    topic: str
    requested_qos: int


@dataclass(frozen=True)
class ParsedPublish:
    remaining_length: int
    qos: int
    retain: bool
    dup: bool
    topic: str
    packet_identifier: int | None
    payload: bytes


@dataclass
class PacketExchange:
    command: str
    declared_length: int
    socket_payload: bytes
    raw_response: bytes
    received_socket_bytes: bytes
    prompt_seen: bool
    send_status_ok: bool


def configure_logging() -> tuple[logging.Logger, Path]:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"l610_tuya_publish_{stamp}.log"

    logger = logging.getLogger("l610-tuya-publish")
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


def build_subscribe_packet(topic: str) -> tuple[bytes, int]:
    variable_header = struct.pack("!H", SUBSCRIBE_PACKET_ID)
    payload = mqtt_utf8(topic) + b"\x01"
    remaining_length = len(variable_header) + len(payload)
    return b"\x82" + encode_remaining_length(remaining_length) + variable_header + payload, remaining_length


def parse_subscribe_packet(packet: bytes) -> ParsedSubscribe:
    if not packet or packet[0] != 0x82:
        raise ValueError("SUBSCRIBE fixed header must be 0x82")
    remaining_length, used = decode_remaining_length(packet)
    offset = 1 + used
    if offset + remaining_length != len(packet):
        raise ValueError("SUBSCRIBE Remaining Length mismatch")
    if offset + 4 > len(packet):
        raise ValueError("SUBSCRIBE is truncated")
    packet_identifier = struct.unpack_from("!H", packet, offset)[0]
    offset += 2
    topic_length = struct.unpack_from("!H", packet, offset)[0]
    offset += 2
    topic_end = offset + topic_length
    if topic_end + 1 != len(packet):
        raise ValueError("SUBSCRIBE topic length or QoS byte is malformed")
    topic = packet[offset:topic_end].decode("utf-8")
    requested_qos = packet[topic_end]
    return ParsedSubscribe(
        remaining_length=remaining_length,
        packet_identifier=packet_identifier,
        topic=topic,
        requested_qos=requested_qos,
    )


def validate_subscribe_packet(packet: bytes, expected_topic: str) -> ParsedSubscribe:
    parsed = parse_subscribe_packet(packet)
    assert parsed.packet_identifier == SUBSCRIBE_PACKET_ID
    assert parsed.topic == expected_topic
    assert parsed.requested_qos == 1
    return parsed


def build_property_json() -> tuple[str, int, bytes, dict[str, object]]:
    timestamp_ms = int(time.time() * 1000)
    msg_id = "l610" + uuid.uuid4().hex[:28]
    payload: dict[str, object] = {
        "msgId": msg_id,
        "time": timestamp_ms,
        "sys": {"ack": 1},
        "data": {
            "action_confidence": {
                "value": ACTION_CONFIDENCE,
                "time": timestamp_ms,
            }
        },
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(msg_id) > 32:
        raise AssertionError("msgId exceeds 32 characters")
    return msg_id, timestamp_ms, encoded, payload


def build_publish_packet(topic: str, payload: bytes) -> tuple[bytes, int]:
    variable_header = mqtt_utf8(topic) + struct.pack("!H", PUBLISH_PACKET_ID)
    remaining_length = len(variable_header) + len(payload)
    return b"\x32" + encode_remaining_length(remaining_length) + variable_header + payload, remaining_length


def parse_publish_packet(packet: bytes) -> ParsedPublish:
    if not packet or packet[0] >> 4 != 3:
        raise ValueError("packet is not MQTT PUBLISH")
    qos = (packet[0] >> 1) & 0x03
    if qos == 3:
        raise ValueError("PUBLISH contains reserved QoS value 3")
    remaining_length, used = decode_remaining_length(packet)
    offset = 1 + used
    packet_end = offset + remaining_length
    if packet_end != len(packet):
        raise ValueError("PUBLISH Remaining Length mismatch")
    if offset + 2 > packet_end:
        raise ValueError("PUBLISH topic length is truncated")
    topic_length = struct.unpack_from("!H", packet, offset)[0]
    offset += 2
    topic_end = offset + topic_length
    if topic_end > packet_end:
        raise ValueError("PUBLISH topic is truncated")
    topic = packet[offset:topic_end].decode("utf-8")
    offset = topic_end
    packet_identifier: int | None = None
    if qos:
        if offset + 2 > packet_end:
            raise ValueError("PUBLISH packet identifier is truncated")
        packet_identifier = struct.unpack_from("!H", packet, offset)[0]
        offset += 2
    return ParsedPublish(
        remaining_length=remaining_length,
        qos=qos,
        retain=bool(packet[0] & 0x01),
        dup=bool(packet[0] & 0x08),
        topic=topic,
        packet_identifier=packet_identifier,
        payload=packet[offset:packet_end],
    )


def validate_outbound_publish(
    packet: bytes,
    expected_topic: str,
    expected_msg_id: str,
) -> tuple[ParsedPublish, dict[str, object]]:
    parsed = parse_publish_packet(packet)
    assert packet[0] == 0x32
    assert parsed.qos == 1
    assert not parsed.retain
    assert not parsed.dup
    assert parsed.topic == expected_topic
    assert parsed.packet_identifier == PUBLISH_PACKET_ID
    decoded = json.loads(parsed.payload.decode("utf-8"))
    assert decoded["data"]["action_confidence"]["value"] == ACTION_CONFIDENCE
    assert decoded["sys"]["ack"] == 1
    assert decoded["msgId"] == expected_msg_id
    return parsed, decoded


def extract_miprtcp_bytes(raw: bytes, socket_id: int) -> bytes:
    received = bytearray()
    pattern = re.compile(
        rb"\+MIPRTCP:\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9A-Fa-f]+)"
    )
    for match in pattern.finditer(raw):
        if int(match.group(1)) != socket_id:
            continue
        encoded = match.group(3)
        if len(encoded) % 2:
            raise ValueError("MIPRTCP contains an odd number of HEX digits")
        received.extend(bytes.fromhex(encoded.decode("ascii")))
    return bytes(received)


def split_mqtt_packets(data: bytes) -> tuple[list[bytes], bytes]:
    packets: list[bytes] = []
    offset = 0
    while offset < len(data):
        try:
            remaining_length, used = decode_remaining_length(data, offset + 1)
        except ValueError:
            break
        total = 1 + used + remaining_length
        if offset + total > len(data):
            break
        packets.append(data[offset : offset + total])
        offset += total
    return packets, data[offset:]


def has_packet_type(data: bytes, packet_type: int) -> bool:
    packets, _ = split_mqtt_packets(data)
    return any(packet and packet[0] >> 4 == packet_type for packet in packets)


def has_puback_and_response(data: bytes, response_topic: str) -> bool:
    packets, _ = split_mqtt_packets(data)
    puback_seen = False
    response_seen = False
    for packet in packets:
        packet_type = packet[0] >> 4
        if packet_type == 4 and len(packet) == 4:
            puback_seen = struct.unpack_from("!H", packet, 2)[0] == PUBLISH_PACKET_ID
        elif packet_type == 3:
            try:
                response_seen = parse_publish_packet(packet).topic == response_topic
            except ValueError:
                pass
    return puback_seen and response_seen


def send_mqtt_packet(
    connection: serial.Serial,
    logger: logging.Logger,
    socket_id: int,
    packet: bytes,
    response_complete: Callable[[bytes], bool] | None,
    timeout: float = MQTT_RESPONSE_TIMEOUT_SECONDS,
) -> PacketExchange:
    declared_length = len(packet)
    command = f"AT+MIPSEND={socket_id},{declared_length}"

    time.sleep(0.05)
    while connection.in_waiting:
        pending = connection.read(connection.in_waiting)
        if pending:
            log_serial_data(logger, "RX-PENDING/URC", pending)
        time.sleep(0.02)

    command_bytes = command.encode("ascii") + b"\r\n"
    log_serial_data(logger, "TX-ASCII", command_bytes)
    connection.write(command_bytes)
    connection.flush()

    chunks: list[bytes] = []
    prompt_deadline = time.monotonic() + COMMAND_TIMEOUT_SECONDS
    prompt_seen = False
    while time.monotonic() < prompt_deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX-ASCII/URC", chunk)
                aggregate = b"".join(chunks)
                if b">" in aggregate:
                    prompt_seen = True
                    break
                if terminal_error(aggregate):
                    break
        time.sleep(0.02)

    if not prompt_seen:
        return PacketExchange(
            command=command,
            declared_length=declared_length,
            socket_payload=b"",
            raw_response=b"".join(chunks),
            received_socket_bytes=b"",
            prompt_seen=False,
            send_status_ok=False,
        )

    logger.info(
        "MIPSEND LENGTH CHECK | declared=%d | actual_socket_payload=%d",
        declared_length,
        len(packet),
    )
    log_serial_data(logger, "TX-BINARY-SOCKET-PAYLOAD-NO-TERMINATOR", packet)
    connection.write(packet)
    connection.flush()

    deadline = time.monotonic() + timeout
    complete_at: float | None = None
    while time.monotonic() < deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX-ASCII/URC", chunk)
                raw = b"".join(chunks)
                socket_bytes = extract_miprtcp_bytes(raw, socket_id)
                send_ok = any(
                    re.match(
                        rb"\+MIPSEND:\s*"
                        + str(socket_id).encode("ascii")
                        + rb"\s*,\s*0\s*,",
                        line,
                    )
                    for line in response_lines(raw)
                )
                response_ok = response_complete is None or response_complete(socket_bytes)
                if send_ok and response_ok:
                    complete_at = time.monotonic()
                if terminal_error(raw) or b"+MIPSTAT:" in raw:
                    complete_at = time.monotonic()
        elif complete_at is not None and time.monotonic() - complete_at >= 0.50:
            break
        time.sleep(0.02)

    raw = b"".join(chunks)
    received = extract_miprtcp_bytes(raw, socket_id)
    send_status_ok = any(
        re.match(
            rb"\+MIPSEND:\s*" + str(socket_id).encode("ascii") + rb"\s*,\s*0\s*,",
            line,
        )
        for line in response_lines(raw)
    )
    logger.info(
        "MIPSEND RESULT | prompt=%s | status_ok=%s | declared=%d | actual=%d | received=%d",
        prompt_seen,
        send_status_ok,
        declared_length,
        len(packet),
        len(received),
    )
    return PacketExchange(
        command=command,
        declared_length=declared_length,
        socket_payload=packet,
        raw_response=raw,
        received_socket_bytes=received,
        prompt_seen=prompt_seen,
        send_status_ok=send_status_ok,
    )


def parse_suback(packets: list[bytes]) -> tuple[bytes, int]:
    for packet in packets:
        if packet[0] != 0x90:
            continue
        remaining_length, used = decode_remaining_length(packet)
        offset = 1 + used
        if offset + remaining_length != len(packet) or remaining_length < 3:
            raise ValueError("malformed SUBACK")
        packet_id = struct.unpack_from("!H", packet, offset)[0]
        if packet_id != SUBSCRIBE_PACKET_ID:
            raise ValueError(f"SUBACK packet identifier mismatch: {packet_id}")
        return_codes = packet[offset + 2 :]
        if not return_codes or any(code not in {0, 1, 2, 0x80} for code in return_codes):
            raise ValueError("SUBACK contains an invalid return code")
        if any(code == 0x80 for code in return_codes):
            raise ValueError("SUBACK rejected the subscription with 0x80")
        return packet, return_codes[0]
    raise ValueError("SUBACK was not received")


def parse_puback(packets: list[bytes]) -> bytes:
    for packet in packets:
        if packet[0] != 0x40:
            continue
        if packet != b"\x40\x02" + struct.pack("!H", PUBLISH_PACKET_ID):
            raise ValueError(f"PUBACK mismatch: {packet.hex(' ').upper()}")
        return packet
    raise ValueError("PUBACK was not received")


def parse_business_response(
    packets: list[bytes],
    expected_topic: str,
    expected_msg_id: str,
) -> tuple[bytes, ParsedPublish, dict[str, object]]:
    for packet in packets:
        if packet[0] >> 4 != 3:
            continue
        parsed = parse_publish_packet(packet)
        if parsed.topic != expected_topic:
            continue
        decoded = json.loads(parsed.payload.decode("utf-8"))
        if decoded.get("msgId") != expected_msg_id:
            raise ValueError("Tuya response msgId does not match the property report")
        if decoded.get("code") != 0:
            raise ValueError(f"Tuya business response code is {decoded.get('code')!r}")
        return packet, parsed, decoded
    raise ValueError("Tuya property/report_response PUBLISH was not received")


def read_hold_urcs(connection: serial.Serial, logger: logging.Logger, duration: float) -> bytes:
    deadline = time.monotonic() + duration
    chunks: list[bytes] = []
    logger.info("SUCCESS HOLD | seconds=%.1f | repeated_publish=false", duration)
    while time.monotonic() < deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX-HOLD/URC", chunk)
        time.sleep(0.02)
    return b"".join(chunks)


def main() -> int:
    logger, log_path = configure_logging()
    mqtt_connected = False
    subscribe_topic = ""
    suback = b""
    publish_topic = ""
    msg_id = ""
    json_bytes = b""
    publish_packet = b""
    publish_exchange: PacketExchange | None = None
    puback = b""
    response_topic = ""
    response_json: dict[str, object] | None = None
    response_code: int | None = None
    socket_closed = False

    logger.info(
        "L610 TUYA PUBLISH START | port=%s | baudrate=%d | host=%s | remote_port=%d | log=%s",
        SERIAL_PORT,
        BAUDRATE,
        REMOTE_HOST,
        REMOTE_PORT,
        log_path,
    )
    logger.info("BOUNDARY | one property only | one publish only | no property downlink")

    try:
        assert_reference_program_not_running(logger)
        reference = build_reference()
        connect_packet, _ = build_connect_packet(reference)
        validate_connect_packet(connect_packet, reference)

        device_id = reference.client_id.removeprefix("tuyalink_")
        subscribe_topic = f"tylink/{device_id}/thing/property/report_response"
        publish_topic = f"tylink/{device_id}/thing/property/report"

        subscribe_packet, subscribe_remaining = build_subscribe_packet(subscribe_topic)
        parsed_subscribe = validate_subscribe_packet(subscribe_packet, subscribe_topic)
        logger.info(
            "SUBSCRIBE SELF-CHECK | topic=%s | packet_id=%d | qos=%d | remaining_length=%d | total=%d",
            parsed_subscribe.topic,
            parsed_subscribe.packet_identifier,
            parsed_subscribe.requested_qos,
            subscribe_remaining,
            len(subscribe_packet),
        )
        logger.info("SUBSCRIBE HEX BEGIN\n%s\nSUBSCRIBE HEX END", format_hex(subscribe_packet))

        msg_id, timestamp_ms, json_bytes, _ = build_property_json()
        publish_packet, publish_remaining = build_publish_packet(publish_topic, json_bytes)
        parsed_publish, decoded_publish_json = validate_outbound_publish(
            publish_packet,
            publish_topic,
            msg_id,
        )
        logger.info("PUBLISH PRECHECK | topic=%s", publish_topic)
        logger.info("PUBLISH PRECHECK | msgId=%s", msg_id)
        logger.info("PUBLISH PRECHECK | timestamp=%d", timestamp_ms)
        logger.info(
            "PUBLISH PRECHECK | JSON=%s",
            json.dumps(decoded_publish_json, ensure_ascii=False, separators=(",", ":")),
        )
        logger.info("PUBLISH PRECHECK | JSON UTF-8 length=%d", len(json_bytes))
        logger.info(
            "PUBLISH PRECHECK | total=%d | remaining_length=%d | packet_identifier=%d",
            len(publish_packet),
            parsed_publish.remaining_length,
            parsed_publish.packet_identifier,
        )
        if publish_remaining != parsed_publish.remaining_length:
            raise AssertionError("PUBLISH builder/parser Remaining Length mismatch")
        logger.info("PUBLISH HEX BEGIN\n%s\nPUBLISH HEX END", format_hex(publish_packet))
        logger.info(
            "PUBLISH SELF-CHECK | packet_type=PUBLISH | qos=1 | topic_match=true | "
            "packet_identifier=2 | value=9982 | sys_ack=1 | msg_id_match=true"
        )

        with open_serial(SERIAL_PORT, BAUDRATE, COMMAND_TIMEOUT_SECONDS) as connection:
            time.sleep(0.20)
            at_result = send_and_collect(connection, logger, "AT")
            if not at_result.ok:
                raise RuntimeError("COM21 did not return OK for AT")

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

            receive_format = send_and_collect(connection, logger, 'AT+GTSET="IPRFMT",0')
            if not receive_format.ok:
                raise RuntimeError("could not set IPRFMT=0")
            free_query = send_and_collect(connection, logger, "AT+MIPOPEN?")
            free_ids = parse_free_socket_ids(free_query.raw)
            if free_ids is None or SOCKET_ID not in free_ids:
                raise RuntimeError("socket 1 is not free")

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
                    raise RuntimeError("SUBSCRIBE MIPSEND failed")
                subscribe_packets, subscribe_remainder = split_mqtt_packets(
                    subscribe_exchange.received_socket_bytes
                )
                if subscribe_remainder:
                    raise RuntimeError("incomplete MQTT bytes remained after SUBACK wait")
                suback, granted_qos = parse_suback(subscribe_packets)
                logger.info(
                    "SUBACK SUCCESS | hex=%s | packet_id=%d | granted_qos=%d",
                    suback.hex(" ").upper(),
                    SUBSCRIBE_PACKET_ID,
                    granted_qos,
                )

                publish_exchange = send_mqtt_packet(
                    connection,
                    logger,
                    SOCKET_ID,
                    publish_packet,
                    lambda data: has_puback_and_response(data, subscribe_topic),
                )
                if not publish_exchange.send_status_ok:
                    raise RuntimeError("PUBLISH MIPSEND failed")
                publish_packets, publish_remainder = split_mqtt_packets(
                    publish_exchange.received_socket_bytes
                )
                if publish_remainder:
                    raise RuntimeError("incomplete MQTT bytes remained after publish response wait")
                puback = parse_puback(publish_packets)
                logger.info("PUBACK SUCCESS | hex=%s", puback.hex(" ").upper())

                _, inbound_publish, response_json = parse_business_response(
                    publish_packets,
                    subscribe_topic,
                    msg_id,
                )
                response_topic = inbound_publish.topic
                response_code = int(response_json["code"])
                logger.info("TUYA RESPONSE TOPIC | %s", response_topic)
                logger.info(
                    "TUYA RESPONSE JSON | %s",
                    json.dumps(response_json, ensure_ascii=False, separators=(",", ":")),
                )
                logger.info("TUYA BUSINESS ACK SUCCESS | code=%d", response_code)

                if inbound_publish.qos == 1:
                    if inbound_publish.packet_identifier is None:
                        raise RuntimeError("inbound QoS1 response lacks a packet identifier")
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
                        raise RuntimeError("could not PUBACK the inbound Tuya response")
                    logger.info(
                        "INBOUND RESPONSE PUBACK SENT | packet_id=%d | hex=%s",
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
        logger.info(
            "STAGE 5 DEVICE-SIDE RESULT | complete=%s | dashboard_confirmation=pending_user",
            complete,
        )
        return 0 if complete else 8
    except (AssertionError, RuntimeError, ValueError, KeyError, TypeError, serial.SerialException, OSError) as exc:
        logger.error("STAGE 5 STOP | %s", exc)
        return 9
    finally:
        logger.info(
            "FINAL EVIDENCE | mqtt_connect=%s | subscribe_topic=%s | suback=%s | "
            "publish_topic=%s | value=%d | msgId=%s | json_bytes=%s | publish_total=%s | "
            "mipsend_actual=%s | puback=%s | response_topic=%s | response_json=%s | "
            "code=%s | dashboard=pending_user | socket_closed=%s",
            mqtt_connected,
            subscribe_topic or "none",
            suback.hex(" ").upper() if suback else "none",
            publish_topic or "none",
            ACTION_CONFIDENCE,
            msg_id or "none",
            len(json_bytes) if json_bytes else "none",
            len(publish_packet) if publish_packet else "none",
            len(publish_exchange.socket_payload) if publish_exchange else "none",
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
