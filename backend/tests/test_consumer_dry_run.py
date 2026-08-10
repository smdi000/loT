import json

from app.config import Settings
from app.integrations.tuya.consumer import TuyaPulsarDryRunConsumer, _masked, _parse_expected_property


def test_dry_run_captures_only_matching_property(tmp_path) -> None:
    capture = tmp_path / "capture.json"
    consumer = TuyaPulsarDryRunConsumer(
        Settings(),
        expected_property=("action_confidence", 9731),
        capture_path=capture,
    )

    consumer._on_message(
        '{"bizCode":"devicePropertyMessage","dataId":"msg-ignore","data":'
        '{"properties":[{"code":"action_confidence","value":9730}]}}'
    )
    assert not consumer.received.is_set()
    assert not capture.exists()

    consumer._on_message(
        '{"bizCode":"devicePropertyMessage","dataId":"msg-capture","devId":"device-01",'
        '"data":{"properties":[{"code":"action_confidence","value":9731}]}}'
    )
    assert consumer.received.is_set()
    captured = json.loads(capture.read_text(encoding="utf-8"))
    assert captured["dataId"] == _masked("msg-capture")
    assert captured["devId"] == _masked("device-01")


def test_expected_property_parser() -> None:
    assert _parse_expected_property("action_confidence=9731") == ("action_confidence", 9731)
    assert _parse_expected_property("device_status=training") == ("device_status", "training")
