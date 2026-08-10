from __future__ import annotations

import argparse
import logging
import json
import signal
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_session_factory
from app.integrations.tuya.pulsar_sdk import build_authentication, decrypt_message, message_id
from app.services.tuya_ingest import ingest_tuya_message

logger = logging.getLogger(__name__)


def _decode_sdk_message(raw_message: Any) -> dict[str, Any] | None:
    """Convert the official SDK's decrypted JSON string to a mapping."""

    if isinstance(raw_message, str):
        try:
            raw_message = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.error("Ignoring undecodable decrypted Tuya message")
            return None
    if not isinstance(raw_message, dict):
        logger.warning("Ignoring non-object Tuya message: %s", type(raw_message).__name__)
        return None
    return raw_message


def _masked(value: str) -> str:
    return f"{value[:4]}…{value[-4:]}" if len(value) > 8 else "configured"


def _redact_capture(value: Any, key: str | None = None) -> Any:
    """Keep capture structure while masking identifiers in shareable evidence."""

    if isinstance(value, dict):
        return {str(child_key): _redact_capture(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, list):
        return [_redact_capture(item) for item in value]
    if key in {"devId", "deviceId", "productId", "productKey", "dataId", "messageId", "sign"} and isinstance(value, str):
        return _masked(value)
    return value


class TuyaPulsarConsumer:
    """Thin adapter around Tuya's official Python Message Service SDK.

    Tuya's SDK decrypts the Message Service envelope before invoking its listener.
    The business backend only receives the decoded mapping and never handles
    Access Secret, dynamic tokens, or payload decryption details itself.
    """

    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory or get_session_factory()
        self._client: Any | None = None
        self._subscription: Any | None = None
        self._receiver_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _on_message(self, raw_message: Any) -> None:
        raw_message = _decode_sdk_message(raw_message)
        if raw_message is None:
            return
        session = self.session_factory()
        try:
            result = ingest_tuya_message(session, raw_message)
            logger.info(
                "Tuya message persisted id=%s biz_code=%s created=%s processed=%s",
                result.message_id,
                raw_message.get("bizCode", raw_message.get("biz_code", "unknown")),
                result.created,
                result.processed,
            )
        except Exception:
            session.rollback()
            # The official SDK logs the callback error and acknowledges the broker
            # message afterwards. Keep the error free of payload/secrets; production
            # monitoring must alert on this path until a durable retry adapter exists.
            logger.exception("Tuya message persistence failed")
            raise
        finally:
            session.close()

    def start(self) -> None:
        if not self.settings.tuya_pulsar_configured:
            raise RuntimeError("Tuya Pulsar configuration is incomplete")
        try:
            import pulsar
        except ImportError as exc:  # pragma: no cover - exercised by container build
            raise RuntimeError("pulsar-client is required for the Tuya consumer") from exc

        topic_name = self.settings.tuya_pulsar_topic.strip().upper()
        if topic_name not in {"TEST", "PROD"}:
            raise ValueError("TUYA_PULSAR_TOPIC must be TEST or PROD")
        channel = "event-test" if topic_name == "TEST" else "event"
        self._client = pulsar.Client(
            self.settings.tuya_pulsar_url,
            authentication=build_authentication(pulsar, self.settings.tuya_access_id, self.settings.tuya_access_secret),
            tls_allow_insecure_connection=True,  # Tuya's official Python example.
            # SDK INFO logs include topic names containing the Access ID; retain
            # only warnings while this adapter emits its own masked connection log.
            logger=pulsar.ConsoleLogger(pulsar.LoggerLevel.Warn),
        )
        self._subscription = self._client.subscribe(
            f"{self.settings.tuya_access_id}/out/{channel}",
            f"{self.settings.tuya_access_id}-sub",
            consumer_type=pulsar.ConsumerType.Failover,
        )
        self._stop_event.clear()
        self._receiver_thread = threading.Thread(target=self._receive_loop, name="tuya-pulsar-receiver", daemon=True)
        self._receiver_thread.start()
        logger.info(
            "Tuya Pulsar connected access_id=%s url=%s topic=%s",
            _masked(self.settings.tuya_access_id),
            self.settings.tuya_pulsar_url,
            topic_name,
        )

    def _receive_loop(self) -> None:
        assert self._subscription is not None
        try:
            import pulsar
        except ImportError:  # pragma: no cover
            return
        while not self._stop_event.is_set():
            try:
                received = self._subscription.receive(timeout_millis=1_000)
            except pulsar.Timeout:
                continue
            except Exception as exc:
                if not self._stop_event.is_set():
                    logger.warning("Tuya Pulsar receive error type=%s", type(exc).__name__)
                continue
            try:
                decoded = decrypt_message(
                    received.data(),
                    dict(received.properties()),
                    self.settings.tuya_access_secret,
                )
                self._on_message(decoded)
                self._subscription.acknowledge_cumulative(received)
                logger.info("Tuya Pulsar message acknowledged id=%s", message_id(received.message_id()))
            except Exception:
                # Deliberately do not acknowledge unsuccessful processing, so
                # Message Service can redeliver according to the subscription.
                logger.exception("Tuya Pulsar message processing failed")

    def stop(self) -> None:
        self._stop_event.set()
        if self._subscription is not None:
            self._subscription.close()
            self._subscription = None
        if self._client is not None:
            self._client.close()
            self._client = None
        if self._receiver_thread is not None:
            self._receiver_thread.join(timeout=3)
            self._receiver_thread = None
        logger.info("Tuya Pulsar consumer stopped")


class TuyaPulsarDryRunConsumer(TuyaPulsarConsumer):
    """Receive and capture one expected decoded message without a database."""

    def __init__(
        self,
        settings: Settings,
        expected_property: tuple[str, Any] | None,
        capture_path: Path | None,
    ) -> None:
        super().__init__(settings)
        self.expected_property = expected_property
        self.capture_path = capture_path
        self.received = threading.Event()

    def _on_message(self, raw_message: Any) -> None:
        raw = _decode_sdk_message(raw_message)
        if raw is None:
            return
        from app.integrations.tuya.parser import normalize_tuya_message

        normalized = normalize_tuya_message(raw)
        logger.info(
            "Tuya TEST message received biz_code=%s device_id=%s product_id=%s properties=%s",
            normalized.biz_code,
            normalized.device_id,
            normalized.product_id,
            sorted(normalized.properties),
        )
        if self.expected_property:
            key, expected_value = self.expected_property
            if normalized.properties.get(key) != expected_value:
                return
        if self.capture_path:
            self.capture_path.parent.mkdir(parents=True, exist_ok=True)
            self.capture_path.write_text(
                json.dumps(_redact_capture(normalized.raw), ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            logger.info("Captured matching decrypted Tuya message to %s", self.capture_path)
        self.received.set()


def _parse_expected_property(raw: str | None) -> tuple[str, Any] | None:
    if not raw:
        return None
    if "=" not in raw:
        raise ValueError("--expect-property uses code=value, for example action_confidence=9731")
    key, value = raw.split("=", 1)
    if not key:
        raise ValueError("--expect-property code cannot be empty")
    try:
        return key, json.loads(value)
    except json.JSONDecodeError:
        return key, value


def main() -> None:
    parser = argparse.ArgumentParser(description="Tuya Message Service consumer")
    parser.add_argument("--dry-run", action="store_true", help="Receive but do not write PostgreSQL")
    parser.add_argument("--capture", type=Path, help="Write one matching decrypted payload as JSON")
    parser.add_argument("--expect-property", help="Stop after a matching code=value property")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    stop_event = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop_event.set())

    if not settings.tuya_pulsar_configured:
        logger.warning("Tuya Pulsar is disabled until TUYA_* Message Service variables are configured")
        while not stop_event.wait(30):
            pass
        return

    if args.capture and not args.dry_run:
        parser.error("--capture is only available with --dry-run")
    try:
        expected_property = _parse_expected_property(args.expect_property)
    except ValueError as exc:
        parser.error(str(exc))

    consumer: TuyaPulsarConsumer
    if args.dry_run:
        consumer = TuyaPulsarDryRunConsumer(settings, expected_property, args.capture)
    else:
        consumer = TuyaPulsarConsumer(settings)
    try:
        consumer.start()
        while not stop_event.wait(1):
            if args.dry_run and isinstance(consumer, TuyaPulsarDryRunConsumer) and consumer.received.is_set():
                break
    finally:
        consumer.stop()


if __name__ == "__main__":
    main()
