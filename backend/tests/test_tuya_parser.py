from app.integrations.tuya.parser import normalize_tuya_message


def property_message() -> dict:
    return {
        "bizCode": "devicePropertyMessage",
        "dataId": "msg-property-9731",
        "devId": "device-test-01",
        "productId": "product-test-01",
        "t": 1_786_130_965_652,
        "data": {"properties": [{"code": "action_confidence", "value": 9731}]},
    }


def test_normalizes_property_message() -> None:
    message = normalize_tuya_message(property_message())

    assert message.biz_code == "devicePropertyMessage"
    assert message.tuya_msg_id == "msg-property-9731"
    assert message.device_id == "device-test-01"
    assert message.product_id == "product-test-01"
    assert message.properties == {"action_confidence": 9731}
    assert message.event_time is not None
    assert message.event_time is not None


def test_normalizes_official_sdk_property_envelope() -> None:
    """TuyaOpenPulsar keeps this envelope around its decrypted payload."""

    raw = {
        "messageId": "pulsar-message-01",
        "payload": {
            "data": {
                "bizCode": "devicePropertyMessage",
                "bizData": {
                    "dataId": "msg-property-9731",
                    "devId": "device-test-01",
                    "productId": "product-test-01",
                    "properties": [
                        {"code": "action_confidence", "dpId": 101, "time": 1_786_180_936_439, "value": 9731}
                    ],
                },
                "ts": 1_786_180_936_439,
            }
        },
    }

    message = normalize_tuya_message(raw)

    assert message.biz_code == "devicePropertyMessage"
    assert message.tuya_msg_id == "msg-property-9731"
    assert message.device_id == "device-test-01"
    assert message.product_id == "product-test-01"
    assert message.properties == {"action_confidence": 9731}
    assert message.event_time is not None


def test_normalizes_official_pulsar_root_biz_data_envelope() -> None:
    raw = {
        "bizCode": "devicePropertyMessage",
        "bizData": {
            "dataId": "msg-property-root-9731",
            "devId": "device-test-01",
            "productId": "product-test-01",
            "properties": [{"code": "action_confidence", "value": 9731}],
        },
        "ts": 1_786_180_936_439,
    }

    message = normalize_tuya_message(raw)

    assert message.tuya_msg_id == "msg-property-root-9731"
    assert message.device_id == "device-test-01"
    assert message.product_id == "product-test-01"
    assert message.properties == {"action_confidence": 9731}


def test_unknown_biz_code_is_preserved() -> None:
    message = normalize_tuya_message({"bizCode": "futureBizCode", "data": {"value": 1}})

    assert message.biz_code == "futureBizCode"
    assert message.properties == {}
    assert len(message.dedup_key) == 64
