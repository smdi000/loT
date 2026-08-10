import hashlib

from app.integrations.tuya.pulsar_sdk import build_authentication


class FakePulsar:
    @staticmethod
    def AuthenticationBasic(username: str, password: str, mechanism: str):
        return username, password, mechanism


def test_builds_official_tuya_pulsar_basic_auth_shape() -> None:
    access_id = "access-id"
    access_secret = "test-access-secret"

    username, password, mechanism = build_authentication(FakePulsar, access_id, access_secret)

    expected = hashlib.md5(f"{access_id}{hashlib.md5(access_secret.encode()).hexdigest()}".encode()).hexdigest()[8:24]
    assert username == '{"username": "access-id","password"'
    assert password == f'"{expected}"}}'
    assert mechanism == "auth1"
