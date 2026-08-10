"""发现并验证 Fibocom L610 的 Windows AT 串口。

本工具只执行只读 AT 查询，不建立 PDP、TCP、TLS 或 MQTT 连接。
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import serial
from serial.tools import list_ports


DEFAULT_BAUDRATES = (115200, 9600, 57600, 38400, 19200)
IDENTITY_COMMANDS = ("ATI", "AT+CGMM")
STATUS_COMMANDS = ("AT+CGMR", "AT+CPIN?", "AT+CSQ", "AT+CEREG?")
FIBOCOM_MARKERS = ("fibocom", "l610")


@dataclass(frozen=True)
class PortInfo:
    device: str
    description: str
    hwid: str


@dataclass
class CommandResult:
    command: str
    raw: bytes
    has_ok: bool
    has_error: bool

    @property
    def text(self) -> str:
        return self.raw.decode("utf-8", errors="replace")


@dataclass
class ProbeMatch:
    port: PortInfo
    baudrate: int
    identity_results: list[CommandResult]
    is_confirmed_l610: bool


def escaped_bytes(data: bytes) -> str:
    """生成不会丢失 CR/LF 和不可打印字符的单行原始表示。"""
    return data.decode("utf-8", errors="backslashreplace").encode(
        "unicode_escape"
    ).decode("ascii")


def log_serial_data(logger: logging.Logger, direction: str, data: bytes) -> None:
    logger.info(
        "SERIAL %s | bytes=%d | raw=%s | hex=%s",
        direction,
        len(data),
        escaped_bytes(data),
        data.hex(" ").upper(),
    )


def response_lines(data: bytes) -> list[bytes]:
    return [line.strip() for line in re.split(rb"\r?\n", data) if line.strip()]


def has_exact_line(data: bytes, expected: bytes) -> bool:
    return expected in response_lines(data)


def read_response(
    connection: serial.Serial,
    logger: logging.Logger,
    timeout: float,
    quiet_period: float = 0.25,
) -> bytes:
    """读取到总超时，或收到数据后串口连续 quiet_period 秒无新数据。"""
    deadline = time.monotonic() + timeout
    last_data_at: float | None = None
    chunks: list[bytes] = []

    while time.monotonic() < deadline:
        waiting = connection.in_waiting
        if waiting:
            chunk = connection.read(waiting)
            if chunk:
                chunks.append(chunk)
                log_serial_data(logger, "RX", chunk)
                last_data_at = time.monotonic()
                if has_exact_line(b"".join(chunks), b"OK") or has_exact_line(
                    b"".join(chunks), b"ERROR"
                ):
                    # 给同一条响应可能紧随其后的字节留出一个短暂窗口。
                    deadline = min(deadline, time.monotonic() + quiet_period)
        elif last_data_at is not None and time.monotonic() - last_data_at >= quiet_period:
            break
        time.sleep(0.02)

    return b"".join(chunks)


def send_command(
    connection: serial.Serial,
    logger: logging.Logger,
    command: str,
    timeout: float,
) -> CommandResult:
    payload = command.encode("ascii") + b"\r\n"
    connection.reset_input_buffer()
    log_serial_data(logger, "TX", payload)
    connection.write(payload)
    connection.flush()
    raw = read_response(connection, logger, timeout=timeout)
    result = CommandResult(
        command=command,
        raw=raw,
        has_ok=has_exact_line(raw, b"OK"),
        has_error=has_exact_line(raw, b"ERROR")
        or any(line.startswith(b"+CME ERROR") for line in response_lines(raw)),
    )
    logger.info(
        "COMMAND RESULT | command=%s | ok=%s | error=%s | total_rx_bytes=%d",
        command,
        result.has_ok,
        result.has_error,
        len(raw),
    )
    return result


def enumerate_ports(logger: logging.Logger) -> list[PortInfo]:
    ports = [
        PortInfo(
            device=port.device,
            description=port.description or "",
            hwid=port.hwid or "",
        )
        for port in list_ports.comports()
    ]
    logger.info("COM PORT ENUMERATION | count=%d", len(ports))
    for port in ports:
        logger.info(
            "COM PORT | device=%s | description=%s | hwid=%s",
            port.device,
            port.description,
            port.hwid,
        )
    return ports


def suspicion_score(port: PortInfo) -> int:
    combined = f"{port.description} {port.hwid}".lower()
    score = 0
    if "fibocom" in combined:
        score += 100
    if "l610" in combined:
        score += 100
    if "at" in combined:
        score += 30
    if "modem" in combined:
        score += 20
    if "usb" in combined or "serial" in combined:
        score += 10
    if "bluetooth" in combined or "bth" in combined:
        score -= 100
    return score


def ordered_candidates(ports: Iterable[PortInfo]) -> list[PortInfo]:
    return sorted(ports, key=lambda port: (-suspicion_score(port), port.device))


def open_serial(port: str, baudrate: int, timeout: float) -> serial.Serial:
    connection = serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.05,
        write_timeout=timeout,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )
    # 避免主动保持硬件流控线；USB AT 口通常不依赖这两根线。
    connection.dtr = False
    connection.rts = False
    connection.reset_input_buffer()
    connection.reset_output_buffer()
    return connection


def identify_at_port(
    ports: list[PortInfo],
    baudrates: tuple[int, ...],
    logger: logging.Logger,
    timeout: float,
) -> ProbeMatch | None:
    tentative: ProbeMatch | None = None

    for port in ordered_candidates(ports):
        logger.info(
            "PROBE CANDIDATE | device=%s | score=%d | description=%s | hwid=%s",
            port.device,
            suspicion_score(port),
            port.description,
            port.hwid,
        )
        for baudrate in baudrates:
            logger.info("PROBE START | device=%s | baudrate=%d", port.device, baudrate)
            try:
                with open_serial(port.device, baudrate, timeout) as connection:
                    # 部分模块刚打开端口时需要一个很短的稳定时间。
                    time.sleep(0.15)
                    at_result = send_command(connection, logger, "AT", timeout)
                    if not at_result.has_ok:
                        logger.warning(
                            "PROBE REJECTED | device=%s | baudrate=%d | reason=no exact OK",
                            port.device,
                            baudrate,
                        )
                        continue

                    logger.info(
                        "AT RESPONSE CONFIRMED | device=%s | baudrate=%d",
                        port.device,
                        baudrate,
                    )
                    identity_results = [
                        send_command(connection, logger, command, timeout=5.0)
                        for command in IDENTITY_COMMANDS
                    ]
                    identity_text = "\n".join(
                        result.text for result in identity_results
                    ).lower()
                    confirmed = any(
                        marker in identity_text for marker in FIBOCOM_MARKERS
                    )
                    match = ProbeMatch(
                        port=port,
                        baudrate=baudrate,
                        identity_results=identity_results,
                        is_confirmed_l610=confirmed,
                    )
                    if confirmed:
                        logger.info(
                            "L610 AT PORT CONFIRMED | device=%s | baudrate=%d",
                            port.device,
                            baudrate,
                        )
                        return match
                    if tentative is None:
                        tentative = match
                        logger.warning(
                            "AT口收到OK，但身份响应未出现 Fibocom/L610；暂存候选并继续扫描"
                        )
            except (serial.SerialException, OSError) as exc:
                logger.warning(
                    "PROBE OPEN/IO ERROR | device=%s | baudrate=%d | error=%s",
                    port.device,
                    baudrate,
                    exc,
                )

    if tentative is not None:
        logger.warning(
            "未从身份响应确认 Fibocom/L610，使用唯一/首个能够精确回复OK的AT口候选：%s",
            tentative.port.device,
        )
    return tentative


def collect_status(match: ProbeMatch, logger: logging.Logger, timeout: float) -> bool:
    logger.info(
        "STATUS COLLECTION START | device=%s | baudrate=%d",
        match.port.device,
        match.baudrate,
    )
    all_results = list(match.identity_results)
    try:
        with open_serial(match.port.device, match.baudrate, timeout) as connection:
            time.sleep(0.15)
            # 重新确认端口仍可通信；本次AT同样必须精确收到OK。
            at_result = send_command(connection, logger, "AT", timeout)
            if not at_result.has_ok:
                logger.error("AT口重新打开后未收到精确OK，停止状态读取")
                return False
            all_results.extend(
                send_command(connection, logger, command, timeout=5.0)
                for command in STATUS_COMMANDS
            )
    except (serial.SerialException, OSError) as exc:
        logger.error("STATUS COLLECTION IO ERROR | error=%s", exc)
        return False

    logger.info("RAW RESPONSE SUMMARY BEGIN")
    for result in all_results:
        logger.info(
            "RAW RESPONSE | command=%s | bytes=%d | raw=%s | hex=%s",
            result.command,
            len(result.raw),
            escaped_bytes(result.raw),
            result.raw.hex(" ").upper(),
        )
    logger.info("RAW RESPONSE SUMMARY END")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        help="只探测指定COM口，例如 COM12；默认枚举并探测所有端口",
    )
    parser.add_argument(
        "--baud",
        type=int,
        help="只尝试指定波特率；默认依次尝试 115200/9600/57600/38400/19200",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="AT探测响应超时秒数，默认2秒",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "logs",
        help="日志目录，默认是脚本旁的 logs 文件夹",
    )
    return parser.parse_args()


def configure_logging(log_dir: Path) -> tuple[logging.Logger, Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"l610_serial_probe_{timestamp}.log"

    logger = logging.getLogger("l610-serial-probe")
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


def main() -> int:
    args = parse_args()
    logger, log_path = configure_logging(args.log_dir)
    logger.info("L610 SERIAL PROBE START | log=%s", log_path)
    logger.info("PYTHON | version=%s", sys.version.replace("\n", " "))
    logger.info("PYSERIAL | version=%s", serial.VERSION)

    ports = enumerate_ports(logger)
    if args.port:
        selected = [port for port in ports if port.device.upper() == args.port.upper()]
        if not selected:
            logger.error("指定串口不存在于枚举结果中：%s", args.port)
            return 2
        ports = selected
    if not ports:
        logger.error("没有枚举到任何COM口")
        return 2

    baudrates = (args.baud,) if args.baud else DEFAULT_BAUDRATES
    match = identify_at_port(ports, baudrates, logger, args.timeout)
    if match is None:
        logger.error("未找到能够对 AT\\r\\n 精确回复 OK 的串口")
        return 3

    if not collect_status(match, logger, args.timeout):
        return 4

    logger.info(
        "STAGE 1 COMPLETE | AT_PORT=%s | BAUDRATE=%d | CONFIRMED_L610=%s",
        match.port.device,
        match.baudrate,
        match.is_confirmed_l610,
    )
    logger.info("STOP: 未执行PDP、TCP、TLS或MQTT命令")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
