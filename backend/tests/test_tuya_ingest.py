from sqlalchemy import func, select

from app.models import TuyaMessage
from app.services.tuya_ingest import ingest_tuya_message


def property_message() -> dict:
    return {
        "bizCode": "devicePropertyMessage",
        "dataId": "msg-property-9731",
        "devId": "device-test-01",
        "productId": "product-test-01",
        "t": 1_786_130_965_652,
        "data": {"properties": [{"code": "action_confidence", "value": 9731}]},
    }


def test_duplicate_message_is_idempotent(session) -> None:
    first = ingest_tuya_message(session, property_message())
    second = ingest_tuya_message(session, property_message())

    assert first.created is True
    assert second.created is False
    assert session.scalar(select(func.count()).select_from(TuyaMessage)) == 1
    stored = session.scalar(select(TuyaMessage))
    assert stored.biz_code == "devicePropertyMessage"
    assert stored.device_id == "device-test-01"
    assert stored.payload_json["data"]["properties"][0]["code"] == "action_confidence"
    assert stored.payload_json["data"]["properties"][0]["value"] == 9731
    assert stored.processed is True


def test_unknown_biz_code_is_stored_without_processing(session) -> None:
    result = ingest_tuya_message(session, {"bizCode": "futureBizCode", "data": {"sample": True}})

    stored = session.get(TuyaMessage, result.message_id)
    assert result.created is True
    assert stored is not None
    assert stored.biz_code == "futureBizCode"
    assert stored.processed is False
