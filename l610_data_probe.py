"""通过固定的 L610 AT 串口验证蜂窝 IPv4 数据会话。

阶段边界：本工具不会执行 MIPOPEN、TLS 或 MQTT 命令，也不会修改 APN。
"""

from __future__ import annotations

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
COMMAND_TIMEOUT_SECONDS = 8.0
MIPCALL_TIMEOUT_SECONDS = 65.0
PING_TIMEOUT_SECONDS = 30.0
PING_TARGET = "8.8.8.8"

READ_ONLY_COMMANDS = (
    "AT",
    "AT+CPIN?",
    "AT+CEREG?",
    "AT+COPS?",
    "AT+CGATT?",
    "AT+CGDCONT?",
    "AT+MIPCALL?",
)


@dataclass
class CommandResult:
    command: str
    raw: bytes
    timed_out: bool

    @property
    def lines(self) -> list[bytes]:
        return response_lines(self.raw)

    @property
    def ok(self) -> bool:
        return b"OK" in self.lines

    @property
    def error(self) -> bool:
        return b"ERROR" in self.lines or any(
            line.startswith((b"+CME ERROR", b"+CMS ERROR")) for line in self.lines
        )

    @property
    def text(self) -> str:
        return self.raw.decode("utf-8", errors="replace")


def configure_logging() -> tuple[logging.Logger, Path]:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"l610_data_probe_{timestamp}.log"

    logger = logging.getLogger("l610-data-probe")
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


def drain_pending(connection: serial.Serial, logger: logging.Logger) -> None:
    """发送新命令前记录所有待处理 URC，不静默丢弃串口数据。"""
    time.sleep(0.05)
    while connection.in_waiting:
        pending = connection.read(connection.in_waiting)
        if pending:
            log_serial_data(logger, "RX-PENDING", pending)
        time.sleep(0.02)


def has_terminal_error(data: bytes) -> bool:
    lines = response_lines(data)
    return b"ERROR" in lines or any(
        line.startswith((b"+CME ERROR", b"+CMS ERROR")) for line in lines
    )


def simple_complete(data: bytes) -> bool:
    lines = response_lines(data)
    return b"OK" in lines or has_terminal_error(data)


def valid_ipv4_from_mipcall(data: bytes) -> str | None:
    text = data.decode("ascii", errors="ignore")
    for line in text.replace("\r", "\n").split("\n"):
        if "+MIPCALL:" not in line:
            continue
        for candidate in re.findall(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", line):
            try:
                address = ipaddress.IPv4Address(candidate)
            except ipaddress.AddressValueError:
                continue
            if not address.is_unspecified:
                return str(address)
    return None


def mipcall_status(data: bytes) -> int | None:
    text = data.decode("ascii", errors="ignore")
    match = re.search(r"\+MIPCALL:\s*([012])(?:\s*,|\s*$)", text, re.MULTILINE)
    return int(match.group(1)) if match else None


def mipcall_dial_complete(data: bytes) -> bool:
    if has_terminal_error(data) or valid_ipv4_from_mipcall(data):
        return True
    return any(line.strip() == b"+MIPCALL: 0" for line in response_lines(data))


def mping_complete(data: bytes) -> bool:
    if has_terminal_error(data):
        return True
    return any(
        re.match(rb"\+MPINGSTAT:\s*(?:0|2)(?:\s*,|\s*$)", line)
        for line in response_lines(data)
    )


def send_and_collect(
    connection: serial.Serial,
    logger: logging.Logger,
    command: str,
    timeout: float,
    completion: Callable[[bytes], bool] = simple_complete,
    quiet_period: float = 0.30,
) -> CommandResult:
    drain_pending(connection, logger)
    payload = command.encode("ascii") + b"\r\n"
    log_serial_data(logger, "TX", payload)
    connection.write(payload)
    connection.flush()

    started_at = time.monotonic()
    deadline = started_at + timeout
    completion_seen_at: float | None = None
    chunks: list[bytes] = []

    while time.monotonic() < deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX", chunk)
                aggregate = b"".join(chunks)
                if completion(aggregate):
                    completion_seen_at = time.monotonic()
        elif (
            completion_seen_at is not None
            and time.monotonic() - completion_seen_at >= quiet_period
        ):
            break
        time.sleep(0.02)

    raw = b"".join(chunks)
    timed_out = not completion(raw)
    result = CommandResult(command=command, raw=raw, timed_out=timed_out)
    logger.info(
        "COMMAND RESULT | command=%s | ok=%s | error=%s | timed_out=%s | total_rx_bytes=%d | elapsed=%.3fs",
        command,
        result.ok,
        result.error,
        result.timed_out,
        len(raw),
        time.monotonic() - started_at,
    )
    return result


def extract_prefixed_lines(result: CommandResult, prefix: bytes) -> list[str]:
    return [
        line.decode("utf-8", errors="replace")
        for line in result.lines
        if line.startswith(prefix)
    ]


def extract_apn_contexts(result: CommandResult) -> list[dict[str, str]]:
    contexts: list[dict[str, str]] = []
    pattern = re.compile(
        r'^\+CGDCONT:\s*(?P<cid>\d+),"(?P<pdp_type>[^"]*)",'
        r'"(?P<apn>[^"]*)","(?P<address>[^"]*)"'
    )
    for line in result.text.replace("\r", "\n").split("\n"):
        match = pattern.match(line.strip())
        if match:
            contexts.append(match.groupdict())
    return contexts


def parse_ping_summary(result: CommandResult) -> dict[str, str | int | bool | None]:
    summary: dict[str, str | int | bool | None] = {
        "completed": False,
        "target": PING_TARGET,
        "sent": None,
        "received": None,
        "average_rtt_ms": None,
        "echo_reply_seen": False,
    }
    for line in result.text.replace("\r", "\n").split("\n"):
        line = line.strip()
        reply = re.match(
            r"\+MPING:\s*([^,]+),(\d+),(\d+)(?:,(\d+))?", line
        )
        if reply and reply.group(2) == "0" and reply.group(3) == "0":
            summary["echo_reply_seen"] = True

        status = re.match(
            r"\+MPINGSTAT:\s*(\d+)(?:,([^,]+),(\d+),(\d+)(?:,(\d+))?)?",
            line,
        )
        if status:
            summary["completed"] = status.group(1) == "0"
            if status.group(2):
                summary["target"] = status.group(2)
            if status.group(3):
                summary["sent"] = int(status.group(3))
            if status.group(4):
                summary["received"] = int(status.group(4))
            if status.group(5):
                summary["average_rtt_ms"] = int(status.group(5))
    return summary


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
    logger.info(
        "L610 DATA PROBE START | port=%s | baudrate=%d | log=%s",
        SERIAL_PORT,
        BAUDRATE,
        log_path,
    )
    logger.info("BOUNDARY | no APN changes; no MIPOPEN; no TLS; no MQTT")
    results: list[CommandResult] = []

    try:
        with open_serial(SERIAL_PORT, BAUDRATE, COMMAND_TIMEOUT_SECONDS) as connection:
            time.sleep(0.20)

            status: dict[str, CommandResult] = {}
            for command in READ_ONLY_COMMANDS:
                result = send_and_collect(
                    connection,
                    logger,
                    command,
                    timeout=COMMAND_TIMEOUT_SECONDS,
                )
                results.append(result)
                status[command] = result
                if command == "AT" and not result.ok:
                    logger.error("COM21 未对 AT 精确回复 OK，停止")
                    log_raw_summary(logger, results)
                    return 2

            operator_lines = extract_prefixed_lines(status["AT+COPS?"], b"+COPS:")
            attach_lines = extract_prefixed_lines(status["AT+CGATT?"], b"+CGATT:")
            registration_lines = extract_prefixed_lines(
                status["AT+CEREG?"], b"+CEREG:"
            )
            sim_lines = extract_prefixed_lines(status["AT+CPIN?"], b"+CPIN:")
            apn_contexts = extract_apn_contexts(status["AT+CGDCONT?"])
            initial_ip = valid_ipv4_from_mipcall(status["AT+MIPCALL?"].raw)
            initial_mipcall_status = mipcall_status(status["AT+MIPCALL?"].raw)

            logger.info("ANALYSIS | SIM=%s", sim_lines or ["unknown"])
            logger.info("ANALYSIS | OPERATOR=%s", operator_lines or ["unknown"])
            logger.info(
                "ANALYSIS | LTE_REGISTRATION=%s",
                registration_lines or ["unknown"],
            )
            logger.info("ANALYSIS | CGATT=%s", attach_lines or ["unknown"])
            logger.info("ANALYSIS | CGDCONT=%s", apn_contexts or ["unparsed"])
            logger.info(
                "ANALYSIS | MIPCALL_INITIAL_STATUS=%s | MIPCALL_INITIAL_IP=%s",
                initial_mipcall_status,
                initial_ip,
            )

            final_ip = initial_ip
            dial_result: CommandResult | None = None
            confirm_result: CommandResult | None = None

            if final_ip:
                logger.info("MIPCALL already has a valid IPv4; dialing is skipped")
            elif initial_mipcall_status == 2:
                logger.error(
                    "MIPCALL reports BUSY (2). The manual forbids issuing another command before it finishes; stopping without random recovery."
                )
                log_raw_summary(logger, results)
                return 3
            else:
                logger.info("No valid IPv4 found; issuing the authorized AT+MIPCALL=1")
                dial_result = send_and_collect(
                    connection,
                    logger,
                    "AT+MIPCALL=1",
                    timeout=MIPCALL_TIMEOUT_SECONDS,
                    completion=mipcall_dial_complete,
                    quiet_period=0.50,
                )
                results.append(dial_result)
                if dial_result.error:
                    logger.error(
                        "AT+MIPCALL=1 returned ERROR. Stopping without CGACT/CGATT/CFUN/APN changes."
                    )
                    log_raw_summary(logger, results)
                    return 4

                final_ip = valid_ipv4_from_mipcall(dial_result.raw)
                confirm_result = send_and_collect(
                    connection,
                    logger,
                    "AT+MIPCALL?",
                    timeout=COMMAND_TIMEOUT_SECONDS,
                )
                results.append(confirm_result)
                final_ip = final_ip or valid_ipv4_from_mipcall(confirm_result.raw)
                if not final_ip:
                    logger.error(
                        "MIPCALL did not yield a valid IPv4; stopping without configuration changes"
                    )
                    log_raw_summary(logger, results)
                    return 5

            logger.info("VALID IPV4 CONFIRMED | address=%s", final_ip)

            mping_test = send_and_collect(
                connection,
                logger,
                "AT+MPING=?",
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
            results.append(mping_test)
            mping_supported = mping_test.ok and any(
                line.startswith(b"+MPING:") for line in mping_test.lines
            )
            logger.info("MPING SUPPORT | supported=%s", mping_supported)

            ping_result: CommandResult | None = None
            ping_summary: dict[str, str | int | bool | None] | None = None
            if mping_supported:
                ping_result = send_and_collect(
                    connection,
                    logger,
                    f'AT+MPING=1,"{PING_TARGET}"',
                    timeout=PING_TIMEOUT_SECONDS,
                    completion=mping_complete,
                    quiet_period=0.50,
                )
                results.append(ping_result)
                ping_summary = parse_ping_summary(ping_result)
                logger.info("PING ANALYSIS | %s", ping_summary)
            else:
                logger.info("MPING is not explicitly supported by the test response; ping skipped")

            log_raw_summary(logger, results)
            logger.info(
                "STAGE 2 COMPLETE | valid_ipv4=%s | mping_supported=%s | ping=%s",
                final_ip,
                mping_supported,
                ping_summary,
            )
            logger.info("STOP: no MIPOPEN, TLS, or MQTT command was sent")
            return 0
    except (serial.SerialException, OSError) as exc:
        logger.error("SERIAL IO ERROR | %s", exc)
        log_raw_summary(logger, results)
        return 6


if __name__ == "__main__":
    raise SystemExit(main())
