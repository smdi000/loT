from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app
from app.services.tuya_ingest import ingest_tuya_message


def test_health_and_messages_endpoint(session) -> None:
    ingest_tuya_message(
        session,
        {
            "bizCode": "devicePropertyMessage",
            "dataId": "msg-api-9731",
            "devId": "device-api-01",
            "data": {"properties": [{"code": "action_confidence", "value": 9731}]},
        },
    )

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        # TestClient owns an anyio portal thread.  Entering it as a context
        # manager is required to close that thread before pytest teardown.
        with TestClient(app) as client:
            health = client.get("/health")
            messages = client.get("/api/messages")
            devices = client.get("/api/devices")

        assert health.status_code == 200
        assert health.json() == {"status": "ok", "database": "ok"}
        assert messages.status_code == 200
        assert messages.json()[0]["biz_code"] == "devicePropertyMessage"
        assert messages.json()[0]["payload_json"]["data"]["properties"][0]["value"] == 9731
        # Phase 2 scopes device visibility to the authenticated account.
        assert devices.status_code == 401
    finally:
        app.dependency_overrides.clear()
