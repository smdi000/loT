from app.config import Settings
from app.integrations.tuya.consumer import TuyaPulsarConsumer
from app.models import TuyaMessage


def test_consumer_accepts_official_sdk_decrypted_json_string(session) -> None:
    consumer = TuyaPulsarConsumer(Settings(), session_factory=lambda: session)
    consumer._on_message(
        '{"bizCode":"devicePropertyMessage","dataId":"msg-consumer-9731",'
        '"devId":"device-consumer-01","data":{"properties":['
        '{"code":"action_confidence","value":9731}]}}'
    )

    stored = session.query(TuyaMessage).one()
    assert stored.biz_code == "devicePropertyMessage"
    assert stored.payload_json["data"]["properties"][0]["value"] == 9731
