import pytest

from qmzg_edge.config import EdgeConfig, EdgeConfigError


BASE_ENV = {
    "TUYA_PRODUCT_ID": "demo-product",
    "TUYA_DEVICE_ID": "demo-device-001",
    "TUYA_DEVICE_SECRET": "local-test-secret",
}


def test_blank_port_enables_linux_discovery() -> None:
    config = EdgeConfig.from_env({**BASE_ENV, "L610_PORT": ""})
    assert config.l610_port is None
    assert config.requires_port_discovery
    assert "demo-device-001" not in config.safe_description()


def test_explicit_linux_port_wins() -> None:
    config = EdgeConfig.from_env({**BASE_ENV, "L610_PORT": "/dev/ttyUSB3"})
    assert config.l610_port == "/dev/ttyUSB3"
    assert not config.requires_port_discovery


def test_invalid_baud_is_rejected() -> None:
    with pytest.raises(EdgeConfigError, match="baud"):
        EdgeConfig.from_env({**BASE_ENV, "L610_BAUD": "12345"})


def test_accepted_profile_cannot_silently_switch_broker() -> None:
    with pytest.raises(EdgeConfigError, match="restricted"):
        EdgeConfig.from_env({**BASE_ENV, "TUYA_MQTT_HOST": "example.test"})

