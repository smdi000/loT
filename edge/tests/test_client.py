from datetime import datetime, timedelta, timezone

import pytest

from qmzg_edge.config import EdgeConfig
from qmzg_edge.l610.client import EdgeClientState, TuyaEdgeClient
from qmzg_edge.training.models import TrainingSummary


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def probe_modem(self) -> None:
        self.calls.append("probe")

    def ensure_network(self) -> str:
        self.calls.append("network")
        return "10.0.0.1"

    def ensure_tls(self) -> None:
        self.calls.append("tls")

    def connect_mqtt(self) -> None:
        self.calls.append("mqtt")

    def publish_properties(self, values: dict[str, object]) -> str:
        self.calls.append(values)
        return "edge-msg-001"

    def close(self) -> None:
        self.calls.append("close")


def config() -> EdgeConfig:
    return EdgeConfig("product", "demo-device-001", "local-test-secret")


def summary() -> TrainingSummary:
    started = datetime(2026, 8, 11, tzinfo=timezone.utc)
    return TrainingSummary(
        session_id="demo_session_001",
        started_at=started,
        ended_at=started + timedelta(seconds=623),
        duration_sec=623,
        total_reps=57,
        avg_confidence=9670,
        max_elbow_angle=1285,
        max_shoulder_angle=934,
        actions={"curl": 57},
        fault_count=0,
    )


def test_client_initialization_order_and_summary_boundary() -> None:
    backend = FakeBackend()
    client = TuyaEdgeClient(config(), backend)
    client.initialize()
    client.connect()
    receipt = client.report_training_summary(summary())
    client.close()

    assert backend.calls[:4] == ["probe", "network", "tls", "mqtt"]
    assert backend.calls[4]["training_max_shldr_angle"] == 934
    assert receipt.msg_id == "edge-msg-001"
    assert client.state == EdgeClientState.CLOSED


def test_client_rejects_publish_before_connect() -> None:
    with pytest.raises(RuntimeError, match="not connected"):
        TuyaEdgeClient(config(), FakeBackend()).report_training_summary(summary())

