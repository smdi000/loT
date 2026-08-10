from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

from ..config import EdgeConfig
from ..training.models import TrainingSummary
from ..training.summary import build_tuya_property_values


class EdgeClientState(str, Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    CONNECTED = "connected"
    CLOSED = "closed"


class L610LinkBackend(Protocol):
    """Low-level boundary to be ported from the accepted Windows golden PoC."""

    def probe_modem(self) -> None: ...
    def ensure_network(self) -> str: ...
    def ensure_tls(self) -> None: ...
    def connect_mqtt(self) -> None: ...
    def publish_properties(self, values: Mapping[str, object]) -> str: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class ReportReceipt:
    msg_id: str
    source: str = "tuya_property"


class TuyaEdgeClient:
    """Stable business API; upper-layer Intel training code only talks to this class."""

    def __init__(self, config: EdgeConfig, backend: L610LinkBackend) -> None:
        self.config = config
        self.backend = backend
        self.state = EdgeClientState.CREATED

    def check_modem(self) -> None:
        self.backend.probe_modem()

    def ensure_network(self) -> str:
        return self.backend.ensure_network()

    def ensure_tls(self) -> None:
        self.backend.ensure_tls()

    def initialize(self) -> None:
        if self.state == EdgeClientState.CLOSED:
            raise RuntimeError("closed TuyaEdgeClient cannot be reinitialized")
        self.check_modem()
        self.ensure_network()
        # L610 SSL state is volatile. This check/restore is mandatory on every boot.
        self.ensure_tls()
        self.state = EdgeClientState.INITIALIZED

    def connect(self) -> None:
        if self.state != EdgeClientState.INITIALIZED:
            raise RuntimeError("initialize() must complete before connect()")
        self.backend.connect_mqtt()
        self.state = EdgeClientState.CONNECTED

    def report_property(self, identifier: str, value: object) -> ReportReceipt:
        if self.state != EdgeClientState.CONNECTED:
            raise RuntimeError("MQTT is not connected")
        code = identifier.strip()
        if not code:
            raise ValueError("property identifier is required")
        return ReportReceipt(msg_id=self.backend.publish_properties({code: value}))

    def report_training_summary(self, summary: TrainingSummary) -> ReportReceipt:
        if self.state != EdgeClientState.CONNECTED:
            raise RuntimeError("MQTT is not connected")
        values = build_tuya_property_values(summary)
        return ReportReceipt(msg_id=self.backend.publish_properties(values))

    def close(self) -> None:
        if self.state != EdgeClientState.CLOSED:
            self.backend.close()
        self.state = EdgeClientState.CLOSED

    def __enter__(self) -> "TuyaEdgeClient":
        self.initialize()
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
