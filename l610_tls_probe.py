"""Probe an L610 TLS socket to Tuya over the module's own cellular link.

Stage boundary: this program performs DNS, TCP, and TLS only. It never sends
MQTT CONNECT or any application payload through the socket.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import logging
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import serial

from l610_serial_probe import escaped_bytes, log_serial_data, open_serial, response_lines


SERIAL_PORT = "COM21"
BAUDRATE = 115200
REMOTE_HOST = "m1.tuyacn.com"
REMOTE_PORT = 8883

COMMAND_TIMEOUT_SECONDS = 8.0
MIPCALL_TIMEOUT_SECONDS = 65.0
MIPOPEN_TIMEOUT_SECONDS = 65.0
SOCKET_HOLD_SECONDS = 7.0

CERTIFICATE_PATH = (
    Path(__file__).resolve().parent / "certs" / "tuya_go_daddy_root_g2.cer"
)
# Official Tuya download: Go Daddy Root Certificate Authority - G2 (DER).
CERTIFICATE_SHA256 = "45140b3247eb9cc8c5b4f0d7b53091f73292089e6e5a63e2749dd3aca9198eda"


@dataclass
class CommandResult:
    command: str
    raw: bytes
    completed: bool

    @property
    def lines(self) -> list[bytes]:
        return response_lines(self.raw)

    @property
    def ok(self) -> bool:
        return b"OK" in self.lines

    @property
    def error(self) -> bool:
        return terminal_error(self.raw)

    @property
    def text(self) -> str:
        return self.raw.decode("utf-8", errors="replace")


def configure_logging() -> tuple[logging.Logger, Path]:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"l610_tls_probe_{stamp}.log"

    logger = logging.getLogger("l610-tls-probe")
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


def terminal_error(data: bytes) -> bool:
    lines = response_lines(data)
    return b"ERROR" in lines or any(
        line.startswith((b"+CME ERROR", b"+CMS ERROR")) for line in lines
    )


def simple_complete(data: bytes) -> bool:
    return b"OK" in response_lines(data) or terminal_error(data)


def mipcall_dial_complete(data: bytes) -> bool:
    if terminal_error(data) or valid_ipv4(data):
        return True
    return any(line.strip() == b"+MIPCALL: 0" for line in response_lines(data))


def mipopen_complete(socket_id: int) -> Callable[[bytes], bool]:
    success_or_inactive = re.compile(
        rb"\+MIPOPEN:\s*" + str(socket_id).encode("ascii") + rb"\s*,\s*[01](?:\s*,|\s*$)"
    )
    socket_status = re.compile(
        rb"\+MIPSTAT:\s*" + str(socket_id).encode("ascii") + rb"\s*,"
    )

    def complete(data: bytes) -> bool:
        if terminal_error(data):
            return True
        return any(
            success_or_inactive.search(line) or socket_status.search(line)
            for line in response_lines(data)
        )

    return complete


def mipclose_complete(socket_id: int) -> Callable[[bytes], bool]:
    pattern = re.compile(
        rb"\+MIPCLOSE:\s*" + str(socket_id).encode("ascii") + rb"(?:\s*,|\s*$)"
    )

    def complete(data: bytes) -> bool:
        return terminal_error(data) or any(
            pattern.search(line) for line in response_lines(data)
        )

    return complete


def drain_pending(connection: serial.Serial, logger: logging.Logger) -> None:
    """Record pending URCs before issuing another command; never discard them."""
    time.sleep(0.05)
    while connection.in_waiting:
        chunk = connection.read(connection.in_waiting)
        if chunk:
            log_serial_data(logger, "RX-PENDING/URC", chunk)
        time.sleep(0.02)


def send_and_collect(
    connection: serial.Serial,
    logger: logging.Logger,
    command: str,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
    completion: Callable[[bytes], bool] = simple_complete,
    quiet_period: float = 0.30,
) -> CommandResult:
    drain_pending(connection, logger)
    payload = command.encode("ascii") + b"\r\n"
    log_serial_data(logger, "TX-ASCII", payload)
    connection.write(payload)
    connection.flush()

    started = time.monotonic()
    deadline = started + timeout
    completed_at: float | None = None
    chunks: list[bytes] = []

    while time.monotonic() < deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX-ASCII/URC", chunk)
                if completion(b"".join(chunks)):
                    completed_at = time.monotonic()
        elif completed_at is not None and time.monotonic() - completed_at >= quiet_period:
            break
        time.sleep(0.02)

    raw = b"".join(chunks)
    completed = completion(raw)
    result = CommandResult(command=command, raw=raw, completed=completed)
    logger.info(
        "COMMAND RESULT | command=%s | ok=%s | error=%s | completed=%s | "
        "rx_bytes=%d | elapsed=%.3fs",
        command,
        result.ok,
        result.error,
        result.completed,
        len(raw),
        time.monotonic() - started,
    )
    return result


def read_for_duration(
    connection: serial.Serial,
    logger: logging.Logger,
    duration: float,
) -> bytes:
    logger.info("SOCKET HOLD START | duration=%.1fs | no application bytes will be sent", duration)
    deadline = time.monotonic() + duration
    chunks: list[bytes] = []
    while time.monotonic() < deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX-HOLD/URC", chunk)
        time.sleep(0.02)
    raw = b"".join(chunks)
    logger.info("SOCKET HOLD END | rx_bytes=%d", len(raw))
    return raw


def valid_ipv4(data: bytes) -> str | None:
    text = data.decode("ascii", errors="ignore")
    for candidate in re.findall(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", text):
        try:
            address = ipaddress.IPv4Address(candidate)
        except ipaddress.AddressValueError:
            continue
        if not address.is_unspecified:
            return str(address)
    return None


def mipcall_status(data: bytes) -> int | None:
    match = re.search(
        rb"\+MIPCALL:\s*([012])(?:\s*,|\s*$)", data.replace(b"\r", b"\n"), re.MULTILINE
    )
    return int(match.group(1)) if match else None


def parse_dns_ipv4(data: bytes) -> str | None:
    text = data.decode("ascii", errors="ignore")
    for line in text.replace("\r", "\n").split("\n"):
        if "+MIPDNS:" not in line:
            continue
        address = valid_ipv4(line.encode("ascii", errors="ignore"))
        if address:
            return address
    return None


def parse_free_socket_ids(data: bytes) -> list[int] | None:
    for line in response_lines(data):
        match = re.match(rb"\+MIPOPEN:\s*(.*)$", line)
        if not match:
            continue
        values = [int(value) for value in re.findall(rb"\d+", match.group(1))]
        if values == [0]:
            return []
        return [value for value in values if 1 <= value <= 6]
    return None


def parse_trustfile_count(data: bytes) -> int | None:
    match = re.search(rb"\+GTSSLFILE:\s*TRUSTFILE\s*,\s*(\d+)", data)
    return int(match.group(1)) if match else None


def parse_single_integer(data: bytes, prefix: bytes) -> int | None:
    match = re.search(re.escape(prefix) + rb"\s*(-?\d+)", data)
    return int(match.group(1)) if match else None


def load_official_trust_certificate(
    connection: serial.Serial,
    logger: logging.Logger,
) -> CommandResult:
    der = CERTIFICATE_PATH.read_bytes()
    actual_digest = hashlib.sha256(der).hexdigest()
    if actual_digest != CERTIFICATE_SHA256:
        raise ValueError(
            f"certificate SHA-256 mismatch: expected {CERTIFICATE_SHA256}, got {actual_digest}"
        )
    body = base64.b64encode(der)
    body_lines = [body[index : index + 64] for index in range(0, len(body), 64)]
    # The SSL manual's appendix defines the accepted Base64 certificate format
    # as PEM, including BEGIN/END lines. CR/LF bytes are part of file_len.
    encoded = (
        b"-----BEGIN CERTIFICATE-----\r\n"
        + b"\r\n".join(body_lines)
        + b"\r\n-----END CERTIFICATE-----\r\n"
    )
    if not 4 <= len(encoded) <= 8192:
        raise ValueError(f"Base64 certificate length is outside L610 range: {len(encoded)}")

    logger.info(
        "TRUST CERTIFICATE VERIFIED | path=%s | der_bytes=%d | pem_bytes=%d | "
        "sha256=%s | subject=Go Daddy Root Certificate Authority - G2",
        CERTIFICATE_PATH,
        len(der),
        len(encoded),
        actual_digest,
    )
    command = f'AT+GTSSLFILE="TRUSTFILE",{len(encoded)}'
    drain_pending(connection, logger)
    command_bytes = command.encode("ascii") + b"\r\n"
    log_serial_data(logger, "TX-ASCII", command_bytes)
    connection.write(command_bytes)
    connection.flush()

    started = time.monotonic()
    prompt_deadline = started + COMMAND_TIMEOUT_SECONDS
    chunks: list[bytes] = []
    prompt_seen = False
    while time.monotonic() < prompt_deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX-ASCII", chunk)
                aggregate = b"".join(chunks)
                if b">" in aggregate:
                    prompt_seen = True
                    break
                if terminal_error(aggregate):
                    break
        time.sleep(0.02)

    if not prompt_seen:
        raw = b"".join(chunks)
        logger.error("TRUST CERTIFICATE LOAD | ODM prompt was not received")
        return CommandResult(command=command, raw=raw, completed=terminal_error(raw))

    # Send exactly file_len PEM bytes in ODM mode. Nothing is appended afterward.
    log_serial_data(logger, "TX-BASE64-PEM-CERTIFICATE", encoded)
    connection.write(encoded)
    connection.flush()

    response_deadline = time.monotonic() + 15.0
    completed_at: float | None = None
    while time.monotonic() < response_deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX-ASCII", chunk)
                if simple_complete(b"".join(chunks)):
                    completed_at = time.monotonic()
        elif completed_at is not None and time.monotonic() - completed_at >= 0.30:
            break
        time.sleep(0.02)

    raw = b"".join(chunks)
    result = CommandResult(command=command, raw=raw, completed=simple_complete(raw))
    logger.info(
        "COMMAND RESULT | command=%s | ok=%s | error=%s | completed=%s | rx_bytes=%d",
        command,
        result.ok,
        result.error,
        result.completed,
        len(raw),
    )
    return result


def connection_clock_plausible(data: bytes) -> bool:
    match = re.search(rb"\+CCLK:\s*\"(\d{2})/(\d{2})/(\d{2}),", data)
    if not match:
        return False
    year, month, day = (int(value) for value in match.groups())
    try:
        module_date = datetime(2000 + year, month, day).date()
    except ValueError:
        return False
    delta_days = abs((datetime.now().date() - module_date).days)
    return delta_days <= 1


def socket_open_succeeded(data: bytes, socket_id: int) -> bool:
    pattern = re.compile(
        rb"\+MIPOPEN:\s*" + str(socket_id).encode("ascii") + rb"\s*,\s*1(?:\s*,|\s*$)"
    )
    return any(pattern.search(line) for line in response_lines(data))


def socket_is_active(data: bytes, socket_id: int) -> bool:
    for line in response_lines(data):
        match = re.match(rb"\+MIPCLOSE:\s*(.*)$", line)
        if not match:
            continue
        values = [int(value) for value in re.findall(rb"\d+", match.group(1))]
        return socket_id in values
    return False


def failure_classification(data: bytes, ssl_error: int | None) -> str:
    if ssl_error == -11:
        return "D. certificate/CA or module-time validation failure"
    if ssl_error in {-7, -8, -9, -20}:
        return "C. TLS handshake failure"
    if ssl_error in {-12, -13, -14, -15, -16, -17, -18, -19}:
        return "D. certificate/CA configuration failure"
    if terminal_error(data):
        return "E. MIPOPEN parameter/command failure"
    if b"+MIPSTAT:" in data:
        return "G. socket stack failure; current URC cannot separate TCP from TLS"
    return "G. cannot determine from the current response"


def log_raw_summary(logger: logging.Logger, results: list[CommandResult]) -> None:
    logger.info("RAW RESPONSE SUMMARY BEGIN")
    for result in results:
        logger.info(
            "RAW RESPONSE | command=%s | bytes=%d | raw=%s | hex=%s",
            result.command,
            len(result.raw),
            escaped_bytes(result.raw),
            result.raw.hex(" ").upper(),
        )
    logger.info("RAW RESPONSE SUMMARY END")


def main() -> int:
    logger, log_path = configure_logging()
    results: list[CommandResult] = []
    logger.info(
        "L610 TLS PROBE START | port=%s | baudrate=%d | host=%s | port=%d | log=%s",
        SERIAL_PORT,
        BAUDRATE,
        REMOTE_HOST,
        REMOTE_PORT,
        log_path,
    )
    logger.info("BOUNDARY | DNS/TCP/TLS only; no MIPSEND; no MQTT bytes; no APN changes")

    try:
        with open_serial(SERIAL_PORT, BAUDRATE, COMMAND_TIMEOUT_SECONDS) as connection:
            time.sleep(0.20)

            at_result = send_and_collect(connection, logger, "AT")
            results.append(at_result)
            if not at_result.ok:
                logger.error("STOP | COM21 did not return exact OK for AT")
                return 2

            mipcall_query = send_and_collect(connection, logger, "AT+MIPCALL?")
            results.append(mipcall_query)
            status = mipcall_status(mipcall_query.raw)
            local_ip = valid_ipv4(mipcall_query.raw)
            logger.info("MIPCALL INITIAL | status=%s | ipv4=%s", status, local_ip)

            if status == 0:
                dial = send_and_collect(
                    connection,
                    logger,
                    "AT+MIPCALL=1",
                    timeout=MIPCALL_TIMEOUT_SECONDS,
                    completion=mipcall_dial_complete,
                    quiet_period=0.50,
                )
                results.append(dial)
                if dial.error:
                    logger.error("STOP | AT+MIPCALL=1 returned ERROR; APN remains unchanged")
                    return 3
                confirm = send_and_collect(connection, logger, "AT+MIPCALL?")
                results.append(confirm)
                status = mipcall_status(confirm.raw)
                local_ip = valid_ipv4(confirm.raw) or valid_ipv4(dial.raw)
            elif status == 2:
                logger.error("STOP | MIPCALL is busy; no recovery or configuration change attempted")
                return 3

            if status != 1 or not local_ip:
                logger.error("STOP | no active MIPCALL with a valid IPv4")
                return 3
            logger.info("MIPCALL CONFIRMED | status=1 | ipv4=%s", local_ip)

            dns_command = f'AT+MIPDNS="{REMOTE_HOST}",0'
            # Although the command is normally synchronous, network-side DNS can be slow.
            # Use the same conservative 60-second class of timeout documented for a
            # hostname-based MIPOPEN, plus a small serial margin.
            dns_result = send_and_collect(connection, logger, dns_command, timeout=65.0)
            results.append(dns_result)
            resolved_ip = parse_dns_ipv4(dns_result.raw)
            dns_supported = dns_result.completed and not dns_result.error
            dns_success = resolved_ip is not None
            logger.info(
                "DNS RESULT | command_supported=%s | success=%s | host=%s | ipv4=%s",
                dns_supported,
                dns_success,
                REMOTE_HOST,
                resolved_ip,
            )
            if not dns_result.completed:
                logger.error("STOP | CLASSIFICATION=A. DNS command produced no final response in 65 seconds")
                return 4
            if dns_supported and not dns_success:
                logger.error("STOP | CLASSIFICATION=A. DNS command completed without an IPv4")
                return 4
            if not dns_supported:
                logger.warning(
                    "MIPDNS is not supported by this firmware response; MIPOPEN will resolve the hostname directly"
                )

            clock_result = send_and_collect(connection, logger, "AT+CCLK?")
            results.append(clock_result)
            if not clock_result.ok or not connection_clock_plausible(clock_result.raw):
                logger.error(
                    "STOP | CLASSIFICATION=D. module clock is unavailable or differs from the current date; "
                    "verified TLS certificate dates cannot be trusted"
                )
                return 5

            version_query = send_and_collect(connection, logger, "AT+GTSSLVER?")
            results.append(version_query)
            ssl_version = parse_single_integer(version_query.raw, b"+GTSSLVER:")
            if version_query.error or ssl_version is None:
                logger.error("STOP | CLASSIFICATION=E. GTSSLVER is unsupported or unparseable")
                return 5
            if ssl_version != 4:
                version_set = send_and_collect(connection, logger, "AT+GTSSLVER=4")
                results.append(version_set)
                if not version_set.ok:
                    logger.error("STOP | CLASSIFICATION=E. failed to select TLS 1.2")
                    return 5

            files_query = send_and_collect(connection, logger, "AT+GTSSLFILE?")
            results.append(files_query)
            trust_count = parse_trustfile_count(files_query.raw)
            if files_query.error or trust_count is None:
                logger.error("STOP | CLASSIFICATION=E. GTSSLFILE status is unsupported or unparseable")
                return 5
            certificate_loaded_this_run = False
            if trust_count == 0:
                certificate_result = load_official_trust_certificate(connection, logger)
                results.append(certificate_result)
                if not certificate_result.ok:
                    logger.error("STOP | CLASSIFICATION=D. official Tuya trust certificate could not be loaded")
                    return 5
                files_confirm = send_and_collect(connection, logger, "AT+GTSSLFILE?")
                results.append(files_confirm)
                trust_count = parse_trustfile_count(files_confirm.raw)
                if trust_count is None or trust_count < 1:
                    logger.error("STOP | CLASSIFICATION=D. TRUSTFILE count did not increase")
                    return 5
                certificate_loaded_this_run = True
            else:
                logger.info(
                    "TRUSTFILE already present | count=%d | initial duplicate load skipped",
                    trust_count,
                )

            mode_query = send_and_collect(connection, logger, "AT+GTSSLMODE?")
            results.append(mode_query)
            ssl_mode = parse_single_integer(mode_query.raw, b"+GTSSLMODE:")
            if mode_query.error or ssl_mode is None:
                logger.error("STOP | CLASSIFICATION=E. GTSSLMODE is unsupported or unparseable")
                return 5
            if ssl_mode != 1:
                mode_set = send_and_collect(connection, logger, "AT+GTSSLMODE=1")
                results.append(mode_set)
                if not mode_set.ok:
                    logger.error("STOP | CLASSIFICATION=D. could not enable server certificate verification")
                    return 5

            version_confirm = send_and_collect(connection, logger, "AT+GTSSLVER?")
            results.append(version_confirm)
            mode_confirm = send_and_collect(connection, logger, "AT+GTSSLMODE?")
            results.append(mode_confirm)
            if parse_single_integer(version_confirm.raw, b"+GTSSLVER:") != 4:
                logger.error("STOP | CLASSIFICATION=E. TLS version did not remain TLS 1.2")
                return 5
            if parse_single_integer(mode_confirm.raw, b"+GTSSLMODE:") != 1:
                logger.error("STOP | CLASSIFICATION=D. certificate verification mode did not remain enabled")
                return 5
            logger.info(
                "TLS CONFIG CONFIRMED | TLS1.2=GTSSLVER:4 | verify_server=GTSSLMODE:1 | trustfiles=%d",
                trust_count,
            )

            free_query = send_and_collect(connection, logger, "AT+MIPOPEN?")
            results.append(free_query)
            free_ids = parse_free_socket_ids(free_query.raw)
            if free_query.error or free_ids is None:
                logger.error("STOP | CLASSIFICATION=E. MIPOPEN free-socket query failed")
                return 6
            if not free_ids:
                logger.error("STOP | CLASSIFICATION=F. no free socket resources")
                return 6
            socket_id = free_ids[0]

            open_command = f'AT+MIPOPEN={socket_id},,"{REMOTE_HOST}",{REMOTE_PORT},2'
            logger.info(
                "MIPOPEN PARAMETERS | socket_id=%d | source_port=automatic | remote_host=%s | "
                "remote_port=%d | protocol=2(SSL over IPv4)",
                socket_id,
                REMOTE_HOST,
                REMOTE_PORT,
            )
            open_result = send_and_collect(
                connection,
                logger,
                open_command,
                timeout=MIPOPEN_TIMEOUT_SECONDS,
                completion=mipopen_complete(socket_id),
                quiet_period=0.75,
            )
            results.append(open_result)
            final_urcs = [
                line.decode("ascii", errors="replace")
                for line in open_result.lines
                if line.startswith((b"+MIPOPEN:", b"+MIPSTAT:"))
            ]
            logger.info("MIPOPEN FINAL URC | %s", final_urcs or ["none"])

            if not socket_open_succeeded(open_result.raw, socket_id):
                ssl_error_result = send_and_collect(connection, logger, "AT+GTSSLERR?")
                results.append(ssl_error_result)
                ssl_error = parse_single_integer(ssl_error_result.raw, b"+GTSSLERR:")

                # A pre-existing trust list is opaque: the module exposes only its
                # count. If the SSL engine specifically reports a missing/invalid
                # trust file, load Tuya's verified official root once and retry the
                # identical MIPOPEN command. This is an evidence-driven CA repair,
                # not a protocol/port/signature variant.
                if ssl_error in {-11, -19} and not certificate_loaded_this_run:
                    logger.warning(
                        "TRUSTFILE REPAIR | ssl_error=%s | loading official Tuya PEM once before one identical retry",
                        ssl_error,
                    )
                    certificate_result = load_official_trust_certificate(connection, logger)
                    results.append(certificate_result)
                    if not certificate_result.ok:
                        logger.error("STOP | CLASSIFICATION=D. official Tuya trust certificate could not be loaded")
                        return 7
                    certificate_loaded_this_run = True

                    files_confirm = send_and_collect(connection, logger, "AT+GTSSLFILE?")
                    results.append(files_confirm)
                    repaired_count = parse_trustfile_count(files_confirm.raw)
                    if repaired_count is None or repaired_count <= trust_count:
                        logger.error("STOP | CLASSIFICATION=D. TRUSTFILE repair was not retained")
                        return 7
                    trust_count = repaired_count

                    retry_free_query = send_and_collect(connection, logger, "AT+MIPOPEN?")
                    results.append(retry_free_query)
                    retry_free_ids = parse_free_socket_ids(retry_free_query.raw)
                    if retry_free_ids is None or socket_id not in retry_free_ids:
                        logger.error("STOP | CLASSIFICATION=F. failed socket was not released for retry")
                        return 7

                    open_result = send_and_collect(
                        connection,
                        logger,
                        open_command,
                        timeout=MIPOPEN_TIMEOUT_SECONDS,
                        completion=mipopen_complete(socket_id),
                        quiet_period=0.75,
                    )
                    results.append(open_result)
                    final_urcs = [
                        line.decode("ascii", errors="replace")
                        for line in open_result.lines
                        if line.startswith((b"+MIPOPEN:", b"+MIPSTAT:"))
                    ]
                    logger.info("MIPOPEN RETRY FINAL URC | %s", final_urcs or ["none"])
                    if socket_open_succeeded(open_result.raw, socket_id):
                        ssl_error = None
                    else:
                        ssl_error_result = send_and_collect(connection, logger, "AT+GTSSLERR?")
                        results.append(ssl_error_result)
                        ssl_error = parse_single_integer(ssl_error_result.raw, b"+GTSSLERR:")

                if socket_open_succeeded(open_result.raw, socket_id):
                    logger.info("MIPOPEN succeeded after the single evidence-driven TRUSTFILE repair")
                else:
                    classification = failure_classification(open_result.raw, ssl_error)
                    logger.error(
                        "STOP | MIPOPEN failed | classification=%s | ssl_error=%s",
                        classification,
                        ssl_error,
                    )
                    return 7

            logger.info(
                "TLS SOCKET ESTABLISHED | socket_id=%d | TCP=true | TLS=true | "
                "evidence=protocol 2 plus final +MIPOPEN state 1",
                socket_id,
            )
            hold_urcs = read_for_duration(connection, logger, SOCKET_HOLD_SECONDS)
            if re.search(rb"\+MIP(?:STAT|CLOSE):\s*" + str(socket_id).encode("ascii"), hold_urcs):
                logger.error("STOP | socket closed asynchronously during the hold period")
                return 8

            active_query = send_and_collect(connection, logger, "AT+MIPCLOSE?")
            results.append(active_query)
            active = active_query.ok and socket_is_active(active_query.raw, socket_id)
            logger.info("SOCKET STATUS AFTER HOLD | socket_id=%d | active=%s", socket_id, active)
            if not active:
                logger.error("STOP | socket was not active after the hold period")
                return 8

            close_result = send_and_collect(
                connection,
                logger,
                f"AT+MIPCLOSE={socket_id}",
                timeout=15.0,
                completion=mipclose_complete(socket_id),
                quiet_period=0.75,
            )
            results.append(close_result)
            close_urcs = [
                line.decode("ascii", errors="replace")
                for line in close_result.lines
                if line.startswith(b"+MIPCLOSE:")
            ]
            logger.info("MIPCLOSE FINAL URC | %s", close_urcs or ["none"])
            if close_result.error or not close_urcs:
                logger.error("STOP | socket close was not confirmed by a final MIPCLOSE URC")
                return 9

            close_confirm = send_and_collect(connection, logger, "AT+MIPCLOSE?")
            results.append(close_confirm)
            still_active = socket_is_active(close_confirm.raw, socket_id)
            logger.info("SOCKET CLOSED CONFIRMATION | socket_id=%d | still_active=%s", socket_id, still_active)
            if still_active:
                logger.error("STOP | socket remains listed as active after MIPCLOSE")
                return 9

            logger.info(
                "STAGE 3 COMPLETE | mipcall=1,%s | dns=%s | resolved_ipv4=%s | "
                "socket_id=%d | tcp=true | tls=true | closed=true",
                local_ip,
                dns_success or socket_open_succeeded(open_result.raw, socket_id),
                resolved_ip,
                socket_id,
            )
            logger.info("STOP | no MIPSEND and no MQTT bytes were sent")
            return 0
    except FileNotFoundError as exc:
        logger.error("FILE ERROR | %s", exc)
        return 10
    except ValueError as exc:
        logger.error("VALIDATION ERROR | %s", exc)
        return 10
    except (serial.SerialException, OSError) as exc:
        logger.error("SERIAL IO ERROR | %s", exc)
        return 11
    finally:
        log_raw_summary(logger, results)
        logger.info("LOG PATH | %s", log_path)


if __name__ == "__main__":
    raise SystemExit(main())
