from dataclasses import dataclass, field

from qmzg_edge.l610.serial_transport import PortCandidate, SerialTransport, discover_at_port


@dataclass
class FakePort:
    reads: list[bytes] = field(default_factory=list)
    writes: list[bytes] = field(default_factory=list)
    closed: bool = False

    @property
    def in_waiting(self) -> int:
        return len(self.reads[0]) if self.reads else 0

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)

    def read(self, size: int = 1) -> bytes:
        return self.reads.pop(0)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class FastTransport(SerialTransport):
    def read_until_idle(self, timeout: float = 3.0, idle: float = 0.15) -> bytes:
        return self.port.read(self.port.in_waiting) if self.port.in_waiting else b""


def test_command_appends_exactly_one_crlf() -> None:
    port = FakePort(reads=[b"\r\nOK\r\n"])
    transport = FastTransport(port)
    assert transport.command("AT") == b"\r\nOK\r\n"
    assert port.writes == [b"AT\r\n"]


def test_trustfile_upload_sends_exact_binary_without_trailer() -> None:
    pem = b"-----BEGIN CERTIFICATE-----\r\nQUJD\r\n-----END CERTIFICATE-----\r\n"
    port = FakePort(reads=[b">", b"\r\nOK\r\n"])
    transport = FastTransport(port)
    response = transport.upload_file("TRUSTFILE", pem)
    assert response.endswith(b"OK\r\n")
    assert port.writes == [f'AT+GTSSLFILE="TRUSTFILE",{len(pem)}\r\n'.encode(), pem]


def test_discovery_prefers_fibocom_hint_but_requires_real_ok() -> None:
    candidates = [
        PortCandidate("/dev/ttyUSB0", "generic modem"),
        PortCandidate("/dev/ttyUSB2", "Fibocom L610 AT"),
    ]
    probed: list[str] = []

    def factory(candidate: PortCandidate) -> FastTransport:
        probed.append(candidate.device)
        response = b"\r\nERROR\r\n" if candidate.device.endswith("2") else b"\r\nOK\r\n"
        return FastTransport(FakePort(reads=[response]))

    selected = discover_at_port(candidates, factory)
    assert probed == ["/dev/ttyUSB2", "/dev/ttyUSB0"]
    assert selected.device == "/dev/ttyUSB0"

