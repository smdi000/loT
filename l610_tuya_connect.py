"""Send exactly one hand-built MQTT 3.1.1 CONNECT over an L610 TLS socket.

Stage boundary: this tool never publishes and never subscribes. Tuya credentials
are loaded and generated exclusively through the already verified functions in
tuya_device_test.py.
"""

from __future__ import annotations

import hashlib
import logging
import re
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import serial

from l610_serial_probe import escaped_bytes, log_serial_data, open_serial, response_lines
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
    mipclose_complete,
    mipopen_complete,
    parse_free_socket_ids,
    parse_single_integer,
    parse_trustfile_count,
    send_and_collect,
    socket_is_active,
    socket_open_succeeded,
    terminal_error,
    valid_ipv4,
)
from tuya_device_test import build_mqtt_credentials, load_config


SOCKET_ID = 1
MQTT_KEEPALIVE_SECONDS = 60
CONNACK_TIMEOUT_SECONDS = 20.0
SUCCESS_HOLD_SECONDS = 5.0


@dataclass(frozen=True)
class ConnectReference:
    timestamp: int
    client_id: str
    username: str
    sign_content: str
    password: str
    password_fingerprint: str


@dataclass(frozen=True)
class ParsedConnect:
    remaining_length: int
    protocol: str
    protocol_level: int
    flags: int
    keepalive: int
    client_id: str
    username: str
    password: str


@dataclass
class MqttExchange:
    command: str
    declared_length: int
    socket_payload: bytes
    uart_input: bytes
    raw_response: bytes
    received_socket_bytes: bytes
    prompt_seen: bool
    send_status_ok: bool


def configure_logging() -> tuple[logging.Logger, Path]:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"l610_tuya_connect_{stamp}.log"

    logger = logging.getLogger("l610-tuya-connect")
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


def assert_reference_program_not_running(logger: logging.Logger) -> None:
    """Fail closed if another tuya_device_test.py process is present."""
    powershell = (
        "$current=$PID; "
        "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | "
        "Where-Object { $_.ProcessId -ne $current -and "
        "$_.CommandLine -match '(^|[\\\\/])tuya_device_test\\.py([\\\"'' ]|$)' } | "
        "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", powershell],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"cannot verify Python process list: {detail}")
    matches = [line for line in completed.stdout.splitlines() if line.strip()]
    if matches:
        logger.error("REFERENCE PROCESS ACTIVE | %s", matches)
        raise RuntimeError("tuya_device_test.py is running; refusing a duplicate DeviceID connection")
    logger.info("PROCESS CHECK | tuya_device_test.py running=false")


def build_reference() -> ConnectReference:
    config = load_config()
    timestamp = int(time.time())  # Generated exactly once for this CONNECT attempt.
    client_id, username, password, returned_timestamp = build_mqtt_credentials(
        config.device_id,
        config.device_secret,
        timestamp,
    )
    if returned_timestamp != timestamp:
        raise AssertionError("reference implementation changed the supplied timestamp")
    sign_content = (
        f"deviceId={config.device_id},timestamp={timestamp},secureMode=1,accessType=1"
    )
    return ConnectReference(
        timestamp=timestamp,
        client_id=client_id,
        username=username,
        sign_content=sign_content,
        password=password,
        password_fingerprint=hashlib.sha256(password.encode("utf-8")).hexdigest(),
    )


def mqtt_utf8(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) > 0xFFFF:
        raise ValueError("MQTT UTF-8 string exceeds 65535 bytes")
    if b"\x00" in encoded:
        raise ValueError("MQTT UTF-8 string contains U+0000")
    return struct.pack("!H", len(encoded)) + encoded


def encode_remaining_length(value: int) -> bytes:
    if not 0 <= value <= 268_435_455:
        raise ValueError("MQTT Remaining Length is outside the valid range")
    encoded = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value:
            digit |= 0x80
        encoded.append(digit)
        if not value:
            return bytes(encoded)


def decode_remaining_length(packet: bytes, offset: int = 1) -> tuple[int, int]:
    multiplier = 1
    value = 0
    used = 0
    while True:
        if offset + used >= len(packet) or used >= 4:
            raise ValueError("malformed MQTT Remaining Length")
        digit = packet[offset + used]
        value += (digit & 0x7F) * multiplier
        used += 1
        if not digit & 0x80:
            return value, used
        multiplier *= 128


def build_connect_packet(reference: ConnectReference) -> tuple[bytes, int]:
    variable_header = b"\x00\x04MQTT" + bytes((4, 0xC2)) + struct.pack(
        "!H", MQTT_KEEPALIVE_SECONDS
    )
    payload = b"".join(
        mqtt_utf8(value)
        for value in (reference.client_id, reference.username, reference.password)
    )
    remaining_length = len(variable_header) + len(payload)
    packet = b"\x10" + encode_remaining_length(remaining_length) + variable_header + payload
    return packet, remaining_length


def read_mqtt_utf8(packet: bytes, offset: int) -> tuple[str, int]:
    if offset + 2 > len(packet):
        raise ValueError("truncated MQTT UTF-8 length")
    length = struct.unpack_from("!H", packet, offset)[0]
    offset += 2
    end = offset + length
    if end > len(packet):
        raise ValueError("truncated MQTT UTF-8 bytes")
    return packet[offset:end].decode("utf-8"), end


def parse_connect_packet(packet: bytes) -> ParsedConnect:
    if not packet or packet[0] != 0x10:
        raise ValueError("packet is not MQTT CONNECT")
    remaining_length, remaining_bytes = decode_remaining_length(packet)
    offset = 1 + remaining_bytes
    if offset + remaining_length != len(packet):
        raise ValueError("Remaining Length does not equal actual packet body length")

    protocol, offset = read_mqtt_utf8(packet, offset)
    if offset + 4 > len(packet):
        raise ValueError("truncated MQTT CONNECT variable header")
    protocol_level = packet[offset]
    flags = packet[offset + 1]
    keepalive = struct.unpack_from("!H", packet, offset + 2)[0]
    offset += 4
    client_id, offset = read_mqtt_utf8(packet, offset)
    username, offset = read_mqtt_utf8(packet, offset)
    password, offset = read_mqtt_utf8(packet, offset)
    if offset != len(packet):
        raise ValueError("unexpected bytes after MQTT CONNECT payload")
    return ParsedConnect(
        remaining_length=remaining_length,
        protocol=protocol,
        protocol_level=protocol_level,
        flags=flags,
        keepalive=keepalive,
        client_id=client_id,
        username=username,
        password=password,
    )


def validate_connect_packet(
    packet: bytes,
    reference: ConnectReference,
) -> ParsedConnect:
    parsed = parse_connect_packet(packet)
    assert parsed.protocol == "MQTT"
    assert parsed.protocol_level == 4
    assert parsed.flags == 0xC2
    assert parsed.keepalive == MQTT_KEEPALIVE_SECONDS
    assert parsed.client_id.encode("utf-8") == reference.client_id.encode("utf-8")
    assert parsed.username.encode("utf-8") == reference.username.encode("utf-8")
    assert parsed.password.encode("utf-8") == reference.password.encode("utf-8")
    return parsed


def format_hex(data: bytes, width: int = 16) -> str:
    return "\n".join(
        " ".join(f"{byte:02X}" for byte in data[offset : offset + width])
        for offset in range(0, len(data), width)
    )


def log_reference_and_packet(
    logger: logging.Logger,
    reference: ConnectReference,
    parsed: ParsedConnect,
    packet: bytes,
) -> None:
    logger.info("AUTH REFERENCE | timestamp=%d", reference.timestamp)
    logger.info("AUTH REFERENCE | Client ID=%s", reference.client_id)
    logger.info("AUTH REFERENCE | Username=%s", reference.username)
    logger.info("AUTH REFERENCE | sign content=%s", reference.sign_content)
    logger.info("AUTH REFERENCE | Password length=%d", len(reference.password.encode("utf-8")))
    logger.info("AUTH REFERENCE | Password SHA256 fingerprint=%s", reference.password_fingerprint)
    logger.info("AUTH REFERENCE | DeviceSecret was not printed")
    logger.info(
        "CONNECT LENGTHS | total=%d | remaining_length=%d | client_id=%d | username=%d | password=%d",
        len(packet),
        parsed.remaining_length,
        len(reference.client_id.encode("utf-8")),
        len(reference.username.encode("utf-8")),
        len(reference.password.encode("utf-8")),
    )
    logger.info("CONNECT HEX BEGIN\n%s\nCONNECT HEX END", format_hex(packet))
    logger.info(
        "CONNECT SELF-PARSE | protocol=%s | level=%d | flags=0x%02X | keepalive=%d | "
        "client_id_match=true | username_match=true | password_match=true",
        parsed.protocol,
        parsed.protocol_level,
        parsed.flags,
        parsed.keepalive,
    )


def extract_miprtcp_bytes(raw: bytes, socket_id: int) -> bytes:
    received = bytearray()
    pattern = re.compile(
        rb"\+MIPRTCP:\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9A-Fa-f]+)"
    )
    for match in pattern.finditer(raw):
        if int(match.group(1)) != socket_id:
            continue
        hex_data = match.group(3)
        if len(hex_data) % 2:
            raise ValueError(f"MIPRTCP returned an odd number of HEX digits: {hex_data!r}")
        received.extend(bytes.fromhex(hex_data.decode("ascii")))
    return bytes(received)


def connack_available(raw: bytes, socket_id: int) -> bool:
    try:
        received = extract_miprtcp_bytes(raw, socket_id)
    except ValueError:
        return True
    return len(received) >= 4 or terminal_error(raw) or b"+MIPSTAT:" in raw


def send_mqtt_connect(
    connection: serial.Serial,
    logger: logging.Logger,
    socket_id: int,
    packet: bytes,
) -> MqttExchange:
    declared_length = len(packet)
    command = f"AT+MIPSEND={socket_id},{declared_length}"

    # Preserve pending URCs instead of clearing the UART input buffer.
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

    prompt_deadline = time.monotonic() + COMMAND_TIMEOUT_SECONDS
    chunks: list[bytes] = []
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
        return MqttExchange(
            command=command,
            declared_length=declared_length,
            socket_payload=b"",
            uart_input=b"",
            raw_response=b"".join(chunks),
            received_socket_bytes=b"",
            prompt_seen=False,
            send_status_ok=False,
        )

    # In the prompt-based data-length mode, Data_len is the exact number of UART
    # data bytes accepted and automatically pushed to the socket. Write the MQTT
    # packet itself, not its printable HEX dump. No CR/LF or Ctrl-Z is appended.
    logger.info(
        "MIPSEND LENGTH CHECK | declared=%d | socket_payload=%d | uart_input_bytes=%d",
        declared_length,
        len(packet),
        len(packet),
    )
    log_serial_data(logger, "TX-BINARY-SOCKET-PAYLOAD-NO-TERMINATOR", packet)
    connection.write(packet)
    connection.flush()

    response_deadline = time.monotonic() + CONNACK_TIMEOUT_SECONDS
    completed_at: float | None = None
    while time.monotonic() < response_deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX-ASCII/URC", chunk)
                aggregate = b"".join(chunks)
                if connack_available(aggregate, socket_id):
                    completed_at = time.monotonic()
        elif completed_at is not None and time.monotonic() - completed_at >= 0.50:
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
        "MIPSEND RESULT | prompt=%s | status_ok=%s | declared=%d | "
        "actual_socket_payload=%d | received_socket_bytes=%d",
        prompt_seen,
        send_status_ok,
        declared_length,
        len(packet),
        len(received),
    )
    return MqttExchange(
        command=command,
        declared_length=declared_length,
        socket_payload=packet,
        uart_input=packet,
        raw_response=raw,
        received_socket_bytes=received,
        prompt_seen=prompt_seen,
        send_status_ok=send_status_ok,
    )


def parse_connack(data: bytes) -> tuple[bytes, int]:
    if len(data) < 4:
        raise ValueError(f"CONNACK is shorter than four bytes: {data.hex(' ').upper()}")
    packet = data[:4]
    if packet[0] != 0x20 or packet[1] != 0x02:
        raise ValueError(f"unexpected MQTT response: {packet.hex(' ').upper()}")
    if packet[2] & 0xFE:
        raise ValueError(f"invalid CONNACK acknowledge flags: 0x{packet[2]:02X}")
    if packet[3] > 5:
        raise ValueError(f"invalid MQTT 3.1.1 CONNACK return code: {packet[3]}")
    return packet, packet[3]


def read_hold_urcs(
    connection: serial.Serial,
    logger: logging.Logger,
    duration: float,
) -> bytes:
    deadline = time.monotonic() + duration
    chunks: list[bytes] = []
    logger.info("MQTT SUCCESS HOLD | seconds=%.1f | PUBLISH=false | SUBSCRIBE=false", duration)
    while time.monotonic() < deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX-HOLD/URC", chunk)
        time.sleep(0.02)
    return b"".join(chunks)


def close_socket(
    connection: serial.Serial,
    logger: logging.Logger,
    socket_id: int,
) -> bool:
    close_result = send_and_collect(
        connection,
        logger,
        f"AT+MIPCLOSE={socket_id}",
        timeout=15.0,
        completion=mipclose_complete(socket_id),
        quiet_period=0.75,
    )
    close_urcs = [line for line in close_result.lines if line.startswith(b"+MIPCLOSE:")]
    confirm = send_and_collect(connection, logger, "AT+MIPCLOSE?")
    closed = bool(close_urcs) and not close_result.error and not socket_is_active(
        confirm.raw, socket_id
    )
    logger.info(
        "SOCKET CLOSE | socket_id=%d | final_urc=%s | confirmed_closed=%s",
        socket_id,
        [line.decode("ascii", errors="replace") for line in close_urcs] or ["none"],
        closed,
    )
    return closed


def main() -> int:
    logger, log_path = configure_logging()
    reference: ConnectReference | None = None
    packet = b""
    exchange: MqttExchange | None = None
    connack = b""
    connack_code: int | None = None
    socket_closed = False
    logger.info(
        "L610 TUYA CONNECT START | port=%s | baudrate=%d | host=%s | remote_port=%d | log=%s",
        SERIAL_PORT,
        BAUDRATE,
        REMOTE_HOST,
        REMOTE_PORT,
        log_path,
    )
    logger.info("BOUNDARY | one MQTT CONNECT only; no PUBLISH; no SUBSCRIBE")

    try:
        assert_reference_program_not_running(logger)
        reference = build_reference()
        packet, remaining_length = build_connect_packet(reference)
        parsed = validate_connect_packet(packet, reference)
        if remaining_length != parsed.remaining_length:
            raise AssertionError("builder/parser Remaining Length mismatch")
        log_reference_and_packet(logger, reference, parsed, packet)

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
                raise RuntimeError("TLS version is not the previously validated TLS 1.2 setting")
            if parse_single_integer(mode.raw, b"+GTSSLMODE:") != 1:
                raise RuntimeError("server certificate verification is not enabled")
            trust_count = parse_trustfile_count(files.raw)
            if trust_count is None:
                raise RuntimeError("cannot parse TRUSTFILE state")
            if trust_count == 0:
                cert_result = load_official_trust_certificate(connection, logger)
                if not cert_result.ok:
                    raise RuntimeError("could not restore the official Tuya TRUSTFILE")
                files = send_and_collect(connection, logger, "AT+GTSSLFILE?")
                trust_count = parse_trustfile_count(files.raw)
            if trust_count is None or trust_count < 1:
                raise RuntimeError("no valid TRUSTFILE is available")
            logger.info(
                "TLS PRECONDITION | version=TLS1.2 | verify_server=true | trustfile_count=%d",
                trust_count,
            )

            # Deterministic receive format: MIPRTCP URCs with HEX-encoded data.
            receive_format = send_and_collect(
                connection,
                logger,
                'AT+GTSET="IPRFMT",0',
            )
            if not receive_format.ok:
                raise RuntimeError("could not set documented IPRFMT=0 receive format")

            free_query = send_and_collect(connection, logger, "AT+MIPOPEN?")
            free_ids = parse_free_socket_ids(free_query.raw)
            if free_ids is None or SOCKET_ID not in free_ids:
                raise RuntimeError("socket 1 is not free")

            open_command = f'AT+MIPOPEN={SOCKET_ID},,"{REMOTE_HOST}",{REMOTE_PORT},2'
            open_result = send_and_collect(
                connection,
                logger,
                open_command,
                timeout=MIPOPEN_TIMEOUT_SECONDS,
                completion=mipopen_complete(SOCKET_ID),
                quiet_period=0.75,
            )
            if not socket_open_succeeded(open_result.raw, SOCKET_ID):
                raise RuntimeError(
                    "TLS socket did not receive final +MIPOPEN: 1,1; MQTT CONNECT was not sent"
                )
            logger.info("TLS SOCKET OPEN | socket_id=1 | final_urc=+MIPOPEN: 1,1")

            try:
                exchange = send_mqtt_connect(
                    connection,
                    logger,
                    SOCKET_ID,
                    packet,
                )
                if not exchange.prompt_seen:
                    raise RuntimeError("MIPSEND did not return the data prompt")
                if exchange.declared_length != len(packet):
                    raise AssertionError("MIPSEND declared length differs from CONNECT packet length")
                if exchange.socket_payload != packet:
                    raise AssertionError("actual socket payload differs from CONNECT packet")
                if not exchange.send_status_ok:
                    raise RuntimeError("MIPSEND did not report status 0")

                connack, connack_code = parse_connack(exchange.received_socket_bytes)
                logger.info("CONNACK HEX | %s", connack.hex(" ").upper())
                logger.info("CONNACK PARSED | return_code=%d", connack_code)

                if connack_code == 0:
                    logger.info("MQTT CONNECT SUCCESS")
                    hold = read_hold_urcs(
                        connection,
                        logger,
                        SUCCESS_HOLD_SECONDS,
                    )
                    if re.search(rb"\+MIP(?:STAT|CLOSE):\s*1", hold):
                        logger.warning("socket emitted a close/status URC during the success hold")
                elif connack_code == 5:
                    logger.error(
                        "MQTT CONNECT NOT AUTHORIZED | evidence preserved | timestamp=%d | "
                        "client_id=%s | username=%s | sign_content=%s | password_fingerprint=%s | "
                        "connect_total=%d | mipsend_declared=%d | actual_payload=%d | "
                        "connect_hex=%s | connack=%s",
                        reference.timestamp,
                        reference.client_id,
                        reference.username,
                        reference.sign_content,
                        reference.password_fingerprint,
                        len(packet),
                        exchange.declared_length,
                        len(exchange.socket_payload),
                        packet.hex(" ").upper(),
                        connack.hex(" ").upper(),
                    )
                else:
                    logger.error("MQTT CONNECT FAILED | return_code=%d", connack_code)
            finally:
                socket_closed = close_socket(connection, logger, SOCKET_ID)

        success = connack_code == 0 and socket_closed
        logger.info(
            "STAGE 4 RESULT | mqtt_authenticated=%s | socket_closed=%s | publish=false | subscribe=false",
            connack_code == 0,
            socket_closed,
        )
        return 0 if success else 8
    except (AssertionError, RuntimeError, ValueError, serial.SerialException, OSError) as exc:
        logger.error("STAGE 4 STOP | %s", exc)
        return 9
    finally:
        logger.info(
            "FINAL EVIDENCE | device_suffix=%s | timestamp=%s | client_id_length=%s | "
            "username_length=%s | password_length=%s | connect_total=%s | "
            "mipsend_actual=%s | connack=%s | return_code=%s | authenticated=%s | "
            "socket_closed=%s",
            reference.client_id[-4:] if reference else "unknown",
            reference.timestamp if reference else "unknown",
            len(reference.client_id.encode("utf-8")) if reference else "unknown",
            len(reference.username.encode("utf-8")) if reference else "unknown",
            len(reference.password.encode("utf-8")) if reference else "unknown",
            len(packet) if packet else "unknown",
            len(exchange.socket_payload) if exchange else "unknown",
            connack.hex(" ").upper() if connack else "none",
            connack_code if connack_code is not None else "none",
            connack_code == 0,
            socket_closed,
        )
        logger.info("LOG PATH | %s", log_path)


if __name__ == "__main__":
    raise SystemExit(main())
