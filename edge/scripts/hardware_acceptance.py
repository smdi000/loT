"""Fail-closed stage runner for Phase 5-B Intel field acceptance.

Only ``env``, ``serial`` and ``at`` currently have implementations. Later
stages are deliberately registered but unavailable until their Linux wire
backend is ported and unit-tested from the immutable golden references.
There is intentionally no ``all`` command.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Sequence

EDGE_ROOT = Path(__file__).resolve().parents[1]
if str(EDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(EDGE_ROOT))

from qmzg_edge.l610.serial_transport import (
    PortCandidate,
    SerialTransport,
    discover_at_port,
    system_port_candidates,
)


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_ENV = 10
EXIT_HARDWARE = 11
EXIT_NOT_READY = 20
IMPLEMENTED_STAGES = frozenset({"env", "serial", "at"})
ALL_STAGES = ("env", "serial", "at", "network", "tls", "mqtt", "property", "summary")


def masked_port_rows(candidates: Sequence[PortCandidate]) -> list[dict[str, object]]:
    return [
        {
            "device": candidate.device,
            "description": candidate.description,
            "hwid": candidate.hwid,
            "vid": f"{candidate.vid:04X}" if candidate.vid is not None else None,
            "pid": f"{candidate.pid:04X}" if candidate.pid is not None else None,
            "fibocom_hint": candidate.fibocom_hint,
        }
        for candidate in candidates
    ]


def environment_evidence(repo_root: Path) -> dict[str, object]:
    edge_env = repo_root / "edge" / ".env"
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "user": os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
        "cwd": str(Path.cwd()),
        "edge_env_present": edge_env.is_file(),
        "git_present": (repo_root / ".git").is_dir(),
        "hardware_touched": False,
    }


def open_transport(candidate: PortCandidate, baud: int, timeout: float) -> SerialTransport:
    try:
        import serial
    except ImportError as error:  # pragma: no cover - deployment guard
        raise RuntimeError("pyserial is required; run the conservative bootstrap first") from error
    port = serial.Serial(
        port=candidate.device,
        baudrate=baud,
        timeout=0.05,
        write_timeout=timeout,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )
    port.dtr = False
    port.rts = False
    return SerialTransport(port)


def select_at_port(
    candidates: Sequence[PortCandidate],
    explicit_port: str | None,
    factory: Callable[[PortCandidate], SerialTransport],
) -> PortCandidate:
    selected = list(candidates)
    if explicit_port:
        selected = [candidate for candidate in selected if candidate.device == explicit_port]
        if not selected:
            raise RuntimeError(f"configured serial port was not enumerated: {explicit_port}")
    return discover_at_port(selected, factory)


def run_at_stage(candidate: PortCandidate, baud: int, timeout: float) -> dict[str, object]:
    transport = open_transport(candidate, baud, timeout)
    try:
        responses: dict[str, str] = {}
        for command in ("AT", "ATI", "AT+CGMM", "AT+CGMR", "AT+CPIN?", "AT+CEREG?"):
            raw = transport.command(command, timeout=timeout)
            responses[command] = raw.decode("utf-8", errors="backslashreplace")
        if "OK" not in responses["AT"].replace("\r", "\n").split():
            raise RuntimeError("AT port stopped returning OK")
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "stage": "at",
            "port": candidate.device,
            "baud": baud,
            "responses": responses,
        }
    finally:
        transport.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=ALL_STAGES)
    parser.add_argument("--port", help="explicit Linux tty; otherwise AT-probe all candidates")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    if args.timeout <= 0 or args.timeout > 60:
        print("timeout must be between 0 and 60 seconds", file=sys.stderr)
        return EXIT_USAGE

    if args.stage == "env":
        print(json.dumps(environment_evidence(repo_root), indent=2, ensure_ascii=False))
        return EXIT_OK

    try:
        candidates = system_port_candidates()
    except RuntimeError as error:
        print(f"environment error: {error}", file=sys.stderr)
        return EXIT_ENV

    if args.stage == "serial":
        print(json.dumps({"stage": "serial", "ports": masked_port_rows(candidates)}, indent=2, ensure_ascii=False))
        return EXIT_OK if candidates else EXIT_HARDWARE

    if args.stage not in IMPLEMENTED_STAGES:
        print(
            f"stage '{args.stage}' is intentionally NOT_READY: the Linux L610 wire backend "
            "has not yet been ported and accepted. Follow the matching field prompt; no modem command was sent.",
            file=sys.stderr,
        )
        return EXIT_NOT_READY

    try:
        candidate = select_at_port(
            candidates,
            args.port,
            lambda item: open_transport(item, args.baud, args.timeout),
        )
        evidence = run_at_stage(candidate, args.baud, args.timeout)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"AT stage failed: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_HARDWARE
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
