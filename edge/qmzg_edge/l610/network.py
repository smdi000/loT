from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Protocol


class CommandChannel(Protocol):
    def command(self, command: str, timeout: float = 3.0) -> bytes: ...


@dataclass(frozen=True)
class NetworkState:
    sim_ready: bool
    lte_registered: bool
    attached: bool
    ipv4: str | None


def parse_mipcall(response: bytes) -> str | None:
    text = response.decode("ascii", errors="ignore")
    matches = re.findall(r"\+MIPCALL:\s*(?:1\s*,\s*)?([0-9.]+)", text)
    for value in reversed(matches):
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if address.version == 4 and not address.is_unspecified:
            return value
    return None


def inspect_network(channel: CommandChannel) -> NetworkState:
    cpin = channel.command("AT+CPIN?")
    cereg = channel.command("AT+CEREG?")
    attached = channel.command("AT+CGATT?")
    mipcall = channel.command("AT+MIPCALL?")
    return NetworkState(
        sim_ready=b"+CPIN: READY" in cpin,
        lte_registered=bool(re.search(rb"\+CEREG:\s*\d+\s*,\s*(1|5)", cereg)),
        attached=b"+CGATT: 1" in attached,
        ipv4=parse_mipcall(mipcall),
    )


def ensure_network(channel: CommandChannel) -> str:
    state = inspect_network(channel)
    if not state.sim_ready:
        raise RuntimeError("SIM is not ready")
    if not state.lte_registered:
        raise RuntimeError("L610 is not registered on LTE")
    if not state.attached:
        raise RuntimeError("L610 is not attached to packet service")
    if state.ipv4:
        return state.ipv4
    dial = channel.command("AT+MIPCALL=1", timeout=60.0)
    ipv4 = parse_mipcall(dial) or parse_mipcall(channel.command("AT+MIPCALL?"))
    if not ipv4:
        raise RuntimeError("MIPCALL did not provide a valid IPv4 address")
    return ipv4
