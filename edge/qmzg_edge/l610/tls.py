from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


TLS_VERSION_1_2 = 4
TLS_VERIFY_SERVER = 1


class TlsCommandChannel(Protocol):
    def command(self, command: str, timeout: float = 3.0) -> bytes: ...
    def upload_file(self, file_type: str, payload: bytes, timeout: float = 15.0) -> bytes: ...


@dataclass(frozen=True)
class TlsState:
    version: int | None
    verify_mode: int | None
    trustfile_count: int

    @property
    def ready(self) -> bool:
        return (
            self.version == TLS_VERSION_1_2
            and self.verify_mode == TLS_VERIFY_SERVER
            and self.trustfile_count >= 1
        )


def _single_integer(response: bytes, prefix: bytes) -> int | None:
    match = re.search(re.escape(prefix) + rb"\s*(\d+)", response)
    return int(match.group(1)) if match else None


def parse_tls_state(version: bytes, mode: bytes, files: bytes) -> TlsState:
    count = _single_integer(files, b"+GTSSLFILE: TRUSTFILE,") or 0
    return TlsState(
        version=_single_integer(version, b"+GTSSLVER:"),
        verify_mode=_single_integer(mode, b"+GTSSLMODE:"),
        trustfile_count=count,
    )


def der_certificate_to_pem(der: bytes) -> bytes:
    body = base64.b64encode(der)
    lines = [body[index : index + 64] for index in range(0, len(body), 64)]
    return b"-----BEGIN CERTIFICATE-----\r\n" + b"\r\n".join(lines) + b"\r\n-----END CERTIFICATE-----\r\n"


def load_complete_pem(path: Path) -> bytes:
    raw = path.read_bytes()
    if b"-----BEGIN CERTIFICATE-----" in raw and b"-----END CERTIFICATE-----" in raw:
        payload = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    else:
        payload = der_certificate_to_pem(raw)
    if not 4 <= len(payload) <= 8192:
        raise ValueError("CA PEM is outside the L610 GTSSLFILE size range")
    return payload


class TlsBootstrapper:
    """Restores volatile L610 TLS state before every Tuya connection."""

    def __init__(self, channel: TlsCommandChannel, ca_pem_path: Path) -> None:
        self.channel = channel
        self.ca_pem_path = ca_pem_path

    def inspect(self) -> TlsState:
        return parse_tls_state(
            self.channel.command("AT+GTSSLVER?"),
            self.channel.command("AT+GTSSLMODE?"),
            self.channel.command("AT+GTSSLFILE?"),
        )

    def ensure(self) -> TlsState:
        state = self.inspect()
        if state.version != TLS_VERSION_1_2:
            if b"OK" not in self.channel.command("AT+GTSSLVER=4"):
                raise RuntimeError("failed to set GTSSLVER=4")
        if state.trustfile_count < 1:
            response = self.channel.upload_file("TRUSTFILE", load_complete_pem(self.ca_pem_path))
            if b"OK" not in response:
                raise RuntimeError("failed to upload the accepted complete PEM TRUSTFILE")
        if state.verify_mode != TLS_VERIFY_SERVER:
            if b"OK" not in self.channel.command("AT+GTSSLMODE=1"):
                raise RuntimeError("failed to set GTSSLMODE=1")
        confirmed = self.inspect()
        if not confirmed.ready:
            raise RuntimeError("L610 TLS state verification failed after restore")
        return confirmed
