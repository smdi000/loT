from pathlib import Path

from qmzg_edge.l610.tls import TlsBootstrapper, TlsState, load_complete_pem, parse_tls_state


class FakeTlsChannel:
    def __init__(self, ready: bool) -> None:
        self.ready = ready
        self.commands: list[str] = []
        self.uploads: list[tuple[str, bytes]] = []

    def command(self, command: str, timeout: float = 3.0) -> bytes:
        self.commands.append(command)
        if command == "AT+GTSSLVER=4" or command == "AT+GTSSLMODE=1":
            return b"\r\nOK\r\n"
        if command == "AT+GTSSLVER?":
            return b"+GTSSLVER: 4\r\nOK\r\n" if self.ready else b"+GTSSLVER: 0\r\nOK\r\n"
        if command == "AT+GTSSLMODE?":
            return b"+GTSSLMODE: 1\r\nOK\r\n" if self.ready else b"+GTSSLMODE: 0\r\nOK\r\n"
        if command == "AT+GTSSLFILE?":
            return b"+GTSSLFILE: TRUSTFILE,1\r\nOK\r\n" if self.ready else b"+GTSSLFILE: TRUSTFILE,0\r\nOK\r\n"
        raise AssertionError(command)

    def upload_file(self, file_type: str, payload: bytes, timeout: float = 15.0) -> bytes:
        self.uploads.append((file_type, payload))
        self.ready = True
        return b">\r\nOK\r\n"


def test_tls_state_parser_matches_accepted_configuration() -> None:
    state = parse_tls_state(b"+GTSSLVER: 4", b"+GTSSLMODE: 1", b"+GTSSLFILE: TRUSTFILE,2")
    assert state == TlsState(version=4, verify_mode=1, trustfile_count=2)
    assert state.ready


def test_ready_tls_state_is_not_rewritten() -> None:
    channel = FakeTlsChannel(ready=True)
    bootstrapper = TlsBootstrapper(channel, Path(__file__))  # path is never read when state is ready
    assert bootstrapper.ensure().ready
    assert channel.uploads == []
    assert "AT+GTSSLVER=4" not in channel.commands


def test_volatile_tls_state_is_restored_with_complete_pem() -> None:
    der = Path(__file__).parent / "fixtures" / "public_ca_test.cer"
    channel = FakeTlsChannel(ready=False)
    bootstrapper = TlsBootstrapper(channel, der)
    assert bootstrapper.ensure().ready
    assert "AT+GTSSLVER=4" in channel.commands
    assert "AT+GTSSLMODE=1" in channel.commands
    assert len(channel.uploads) == 1
    _, payload = channel.uploads[0]
    assert payload.startswith(b"-----BEGIN CERTIFICATE-----\r\n")
    assert payload.endswith(b"-----END CERTIFICATE-----\r\n")
    assert payload == load_complete_pem(der)
