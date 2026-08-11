from pathlib import Path
import re

from qmzg_edge.l610.serial_transport import PortCandidate
from scripts.hardware_acceptance import (
    EXIT_NOT_READY,
    environment_evidence,
    main,
    masked_port_rows,
    select_at_port,
)


class FakeTransport:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.closed = False

    def command(self, command: str, timeout: float = 3.0) -> bytes:
        return self.response

    def close(self) -> None:
        self.closed = True


def test_environment_evidence_never_contains_env_values() -> None:
    evidence = environment_evidence(Path(__file__).parents[2])
    assert evidence["hardware_touched"] is False
    assert set(evidence) == {
        "timestamp",
        "platform",
        "machine",
        "python",
        "user",
        "cwd",
        "edge_env_present",
        "git_present",
        "hardware_touched",
    }


def test_serial_rows_preserve_vid_pid_and_fibocom_hint() -> None:
    rows = masked_port_rows([PortCandidate("/dev/ttyUSB3", "Fibocom L610", "USB", 0x2CB7, 0x0001)])
    assert rows == [
        {
            "device": "/dev/ttyUSB3",
            "description": "Fibocom L610",
            "hwid": "USB",
            "vid": "2CB7",
            "pid": "0001",
            "fibocom_hint": True,
        }
    ]


def test_explicit_port_still_requires_at_ok() -> None:
    candidate = PortCandidate("/dev/ttyUSB4", "Fibocom")
    selected = select_at_port([candidate], "/dev/ttyUSB4", lambda _: FakeTransport(b"\r\nOK\r\n"))
    assert selected == candidate


def test_unimplemented_hardware_stage_fails_closed(monkeypatch, capsys) -> None:
    monkeypatch.setattr("scripts.hardware_acceptance.system_port_candidates", lambda: [])
    assert main(["network"]) == EXIT_NOT_READY
    assert "NOT_READY" in capsys.readouterr().err


def test_bootstrap_is_conservative() -> None:
    content = (Path(__file__).parents[1] / "scripts" / "bootstrap_intel.sh").read_text(encoding="utf-8")
    assert not re.search(r"(?m)^\s*sudo\b", content)
    assert not re.search(r"(?m)^\s*reboot\b", content)
    assert not re.search(r"(?m)^\s*systemctl\b", content)
    assert not re.search(r"(?m)^\s*iptables\b", content)
    assert "D:\\code\\" not in content
    assert "/home/" not in content
    assert "--apply" in content
