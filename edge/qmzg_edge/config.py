from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class EdgeConfigError(ValueError):
    """Raised when edge runtime configuration is incomplete or unsafe."""


@dataclass(frozen=True)
class EdgeConfig:
    product_id: str
    device_id: str
    device_secret: str
    l610_port: str | None = None
    l610_baud: int = 115200
    broker_host: str = "m1.tuyacn.com"
    broker_port: int = 8883
    ca_pem_path: Path = Path("certs/tuya_go_daddy_root_g2.cer")

    def __post_init__(self) -> None:
        for name, value in (
            ("TUYA_PRODUCT_ID", self.product_id),
            ("TUYA_DEVICE_ID", self.device_id),
            ("TUYA_DEVICE_SECRET", self.device_secret),
        ):
            if not value.strip():
                raise EdgeConfigError(f"{name} is required")
        if self.l610_baud not in {9600, 19200, 38400, 57600, 115200, 230400}:
            raise EdgeConfigError("L610_BAUD is not a supported serial baud rate")
        if not 1 <= self.broker_port <= 65535:
            raise EdgeConfigError("TUYA_MQTT_PORT must be between 1 and 65535")
        if self.broker_host != "m1.tuyacn.com" or self.broker_port != 8883:
            raise EdgeConfigError("this accepted edge profile is restricted to m1.tuyacn.com:8883")

    @property
    def requires_port_discovery(self) -> bool:
        return not self.l610_port

    def safe_description(self) -> str:
        masked = self.device_id[-4:].rjust(len(self.device_id), "*")
        return (
            f"device={masked}, port={self.l610_port or 'auto-discovery'}, "
            f"baud={self.l610_baud}, broker={self.broker_host}:{self.broker_port}"
        )

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> "EdgeConfig":
        env = values if values is not None else os.environ
        try:
            baud = int(env.get("L610_BAUD", "115200"))
            broker_port = int(env.get("TUYA_MQTT_PORT", "8883"))
        except ValueError as error:
            raise EdgeConfigError("L610_BAUD and TUYA_MQTT_PORT must be integers") from error
        port = env.get("L610_PORT", "").strip() or None
        return cls(
            product_id=env.get("TUYA_PRODUCT_ID", ""),
            device_id=env.get("TUYA_DEVICE_ID", ""),
            device_secret=env.get("TUYA_DEVICE_SECRET", ""),
            l610_port=port,
            l610_baud=baud,
            broker_host=env.get("TUYA_MQTT_HOST", "m1.tuyacn.com"),
            broker_port=broker_port,
            ca_pem_path=Path(env.get("L610_CA_PEM_PATH", "certs/tuya_go_daddy_root_g2.cer")),
        )
