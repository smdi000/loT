from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol


class SerialPortLike(Protocol):
    in_waiting: int

    def write(self, data: bytes) -> int: ...
    def read(self, size: int = 1) -> bytes: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class PortCandidate:
    device: str
    description: str = ""
    hwid: str = ""
    vid: int | None = None
    pid: int | None = None

    @property
    def fibocom_hint(self) -> bool:
        evidence = f"{self.description} {self.hwid}".lower()
        return "fibocom" in evidence or "l610" in evidence


class SerialTransport:
    """Small binary-safe wrapper used by the production L610 layers."""

    def __init__(self, port: SerialPortLike) -> None:
        self.port = port

    def write_raw(self, payload: bytes) -> None:
        written = self.port.write(payload)
        self.port.flush()
        if written != len(payload):
            raise IOError(f"serial short write: expected {len(payload)}, wrote {written}")

    def read_until_idle(self, timeout: float = 3.0, idle: float = 0.15) -> bytes:
        deadline = time.monotonic() + timeout
        last_data = time.monotonic()
        chunks: list[bytes] = []
        while time.monotonic() < deadline:
            waiting = self.port.in_waiting
            if waiting:
                chunk = self.port.read(waiting)
                if chunk:
                    chunks.append(chunk)
                    last_data = time.monotonic()
            elif chunks and time.monotonic() - last_data >= idle:
                break
            time.sleep(0.01)
        return b"".join(chunks)

    def command(self, command: str, timeout: float = 3.0) -> bytes:
        if "\r" in command or "\n" in command:
            raise ValueError("AT command must not contain CR/LF")
        self.write_raw(command.encode("ascii") + b"\r\n")
        return self.read_until_idle(timeout=timeout)

    def upload_file(self, file_type: str, payload: bytes, timeout: float = 15.0) -> bytes:
        """Upload exact PEM bytes using the accepted GTSSLFILE ODM mode."""
        if file_type != "TRUSTFILE":
            raise ValueError("edge bootstrap only permits TRUSTFILE uploads")
        command = f'AT+GTSSLFILE="{file_type}",{len(payload)}'
        self.write_raw(command.encode("ascii") + b"\r\n")
        prompt = self.read_until_idle(timeout=3.0, idle=0.05)
        if b">" not in prompt:
            raise IOError("L610 did not return the GTSSLFILE data prompt")
        self.write_raw(payload)
        return prompt + self.read_until_idle(timeout=timeout)

    def close(self) -> None:
        self.port.close()


def system_port_candidates() -> list[PortCandidate]:
    try:
        from serial.tools import list_ports
    except ImportError as error:  # pragma: no cover - environment guard
        raise RuntimeError("pyserial is required for L610 discovery") from error
    return [
        PortCandidate(
            device=item.device,
            description=item.description or "",
            hwid=item.hwid or "",
            vid=item.vid,
            pid=item.pid,
        )
        for item in list_ports.comports()
    ]


def discover_at_port(
    candidates: Iterable[PortCandidate],
    transport_factory: Callable[[PortCandidate], SerialTransport],
) -> PortCandidate:
    """Probe every candidate and accept only a port that returns an actual AT OK."""
    ordered = sorted(candidates, key=lambda item: (not item.fibocom_hint, item.device))
    errors: list[str] = []
    for candidate in ordered:
        transport: SerialTransport | None = None
        try:
            transport = transport_factory(candidate)
            response = transport.command("AT", timeout=1.5)
            lines = {line.strip() for line in response.replace(b"\r", b"\n").split(b"\n")}
            if b"OK" in lines:
                return candidate
            errors.append(f"{candidate.device}: no OK")
        except (OSError, RuntimeError, ValueError) as error:
            errors.append(f"{candidate.device}: {type(error).__name__}")
        finally:
            if transport is not None:
                transport.close()
    raise RuntimeError("no L610 AT port returned OK; " + ", ".join(errors))
