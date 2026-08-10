"""One-shot Tuya Pulsar connection diagnostic for Phase 4-A deployment."""

from __future__ import annotations

import logging
import os
import sys

import pulsar

sys.path.insert(0, "/app")

from app.integrations.tuya.pulsar_sdk import build_authentication


def main() -> int:
    access_id = os.environ["TUYA_ACCESS_ID"]
    access_secret = os.environ["TUYA_ACCESS_SECRET"]
    url = os.environ["TUYA_PULSAR_URL"]
    topic_name = os.environ.get("TUYA_PULSAR_TOPIC", "TEST").strip().upper()
    channel = "event-test" if topic_name == "TEST" else "event"
    log_level = (
        pulsar.LoggerLevel.Error
        if os.environ.get("PULSAR_DIAGNOSTIC_QUIET") == "1"
        else pulsar.LoggerLevel.Debug
    )

    client = None
    consumer = None
    try:
        client = pulsar.Client(
            url,
            authentication=build_authentication(pulsar, access_id, access_secret),
            tls_allow_insecure_connection=True,
            operation_timeout_seconds=15,
            logger=pulsar.ConsoleLogger(log_level),
        )
        consumer = client.subscribe(
            f"{access_id}/out/{channel}",
            f"{access_id}-sub",
            consumer_type=pulsar.ConsumerType.Failover,
        )
        print("PULSAR_DIAGNOSTIC_RESULT=connected")
        return 0
    except Exception as exc:
        print(f"PULSAR_DIAGNOSTIC_RESULT=failed type={type(exc).__name__}")
        return 1
    finally:
        if consumer is not None:
            consumer.close()
        if client is not None:
            client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
