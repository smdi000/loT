"""Restore the already-accepted L610 TLS settings, then probe one TLS socket.

This tool deliberately stops at TLS.  It does not issue MIPSEND and never
sends MQTT or Tuya application bytes.  The settings and certificate upload
path are reused from the accepted ``l610_tls_probe.py`` implementation and
the 2026-08-07 success log.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from l610_serial_probe import open_serial
from l610_tls_probe import (
    BAUDRATE,
    COMMAND_TIMEOUT_SECONDS,
    MIPCALL_TIMEOUT_SECONDS,
    MIPOPEN_TIMEOUT_SECONDS,
    REMOTE_HOST,
    REMOTE_PORT,
    SERIAL_PORT,
    connection_clock_plausible,
    load_official_trust_certificate,
    mipcall_dial_complete,
    mipcall_status,
    mipclose_complete,
    mipopen_complete,
    parse_free_socket_ids,
    parse_single_integer,
    parse_trustfile_count,
    read_for_duration,
    send_and_collect,
    socket_is_active,
    socket_open_succeeded,
    valid_ipv4,
)


SOCKET_ID = 1
SOCKET_HOLD_SECONDS = 5.0
TLS_VERSION = 4
TLS_VERIFY_MODE = 1


def configure_logging() -> tuple[logging.Logger, Path]:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"l610_tls_restore_{timestamp}.log"

    logger = logging.getLogger("l610_tls_restore")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s.%(msecs)03d | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger, log_path


def ensure_data_connection(connection, logger: logging.Logger) -> str:
    query = send_and_collect(connection, logger, "AT+MIPCALL?")
    status = mipcall_status(query.raw)
    ipv4 = valid_ipv4(query.raw)
    logger.info("MIPCALL INITIAL | status=%s | ipv4=%s", status, ipv4)

    if status == 0:
        dial = send_and_collect(
            connection,
            logger,
            "AT+MIPCALL=1",
            timeout=MIPCALL_TIMEOUT_SECONDS,
            completion=mipcall_dial_complete,
            quiet_period=0.50,
        )
        if dial.error:
            raise RuntimeError("AT+MIPCALL=1 returned ERROR")
        query = send_and_collect(connection, logger, "AT+MIPCALL?")
        status = mipcall_status(query.raw)
        ipv4 = valid_ipv4(query.raw) or valid_ipv4(dial.raw)

    if status != 1 or not ipv4:
        raise RuntimeError("no active MIPCALL with a valid IPv4 address")
    logger.info("MIPCALL CONFIRMED | status=1 | ipv4=%s", ipv4)
    return ipv4


def ensure_ssl_configuration(connection, logger: logging.Logger) -> tuple[int, bool]:
    version_query = send_and_collect(connection, logger, "AT+GTSSLVER?")
    mode_query = send_and_collect(connection, logger, "AT+GTSSLMODE?")
    files_query = send_and_collect(connection, logger, "AT+GTSSLFILE?")

    version = parse_single_integer(version_query.raw, b"+GTSSLVER:")
    mode = parse_single_integer(mode_query.raw, b"+GTSSLMODE:")
    trust_count = parse_trustfile_count(files_query.raw)
    if version is None or mode is None or trust_count is None:
        raise RuntimeError("could not parse current GTSSL state")

    logger.info(
        "TLS CONFIG INITIAL | GTSSLVER=%d | GTSSLMODE=%d | TRUSTFILE_COUNT=%d",
        version,
        mode,
        trust_count,
    )

    if version != TLS_VERSION:
        result = send_and_collect(connection, logger, "AT+GTSSLVER=4")
        if not result.ok:
            raise RuntimeError("accepted GTSSLVER=4 restore command failed")
    else:
        logger.info("GTSSLVER already correct; write skipped")

    certificate_loaded = False
    if trust_count == 0:
        result = load_official_trust_certificate(connection, logger)
        if not result.ok:
            raise RuntimeError("accepted complete PEM TRUSTFILE upload failed")
        certificate_loaded = True
    else:
        logger.info("TRUSTFILE already present; duplicate upload skipped | count=%d", trust_count)

    if mode != TLS_VERIFY_MODE:
        result = send_and_collect(connection, logger, "AT+GTSSLMODE=1")
        if not result.ok:
            raise RuntimeError("accepted GTSSLMODE=1 restore command failed")
    else:
        logger.info("GTSSLMODE already correct; write skipped")

    version_confirm = send_and_collect(connection, logger, "AT+GTSSLVER?")
    mode_confirm = send_and_collect(connection, logger, "AT+GTSSLMODE?")
    files_confirm = send_and_collect(connection, logger, "AT+GTSSLFILE?")
    version = parse_single_integer(version_confirm.raw, b"+GTSSLVER:")
    mode = parse_single_integer(mode_confirm.raw, b"+GTSSLMODE:")
    trust_count = parse_trustfile_count(files_confirm.raw)
    if version != TLS_VERSION or mode != TLS_VERIFY_MODE or not trust_count:
        raise RuntimeError(
            "TLS restore verification failed: expected GTSSLVER=4, GTSSLMODE=1, TRUSTFILE>=1"
        )

    logger.info(
        "TLS CONFIG RESTORED | GTSSLVER=4 | GTSSLMODE=1 | TRUSTFILE_COUNT=%d",
        trust_count,
    )
    return trust_count, certificate_loaded


def open_tls_socket(connection, logger: logging.Logger):
    free_query = send_and_collect(connection, logger, "AT+MIPOPEN?")
    free_ids = parse_free_socket_ids(free_query.raw)
    if free_ids is None:
        raise RuntimeError("could not parse MIPOPEN socket state")
    if SOCKET_ID not in free_ids:
        raise RuntimeError("socket 1 is not free; no existing socket was modified")

    command = f'AT+MIPOPEN={SOCKET_ID},,"{REMOTE_HOST}",{REMOTE_PORT},2'
    logger.info(
        "MIPOPEN PARAMETERS | socket_id=1 | source_port=automatic | remote_host=%s | "
        "remote_port=%d | protocol=2(SSL over IPv4)",
        REMOTE_HOST,
        REMOTE_PORT,
    )
    result = send_and_collect(
        connection,
        logger,
        command,
        timeout=MIPOPEN_TIMEOUT_SECONDS,
        completion=mipopen_complete(SOCKET_ID),
        quiet_period=0.75,
    )
    final_urcs = [
        line.decode("ascii", errors="replace")
        for line in result.lines
        if line.startswith((b"+MIPOPEN:", b"+MIPSTAT:"))
    ]
    logger.info("MIPOPEN FINAL URC | %s", final_urcs or ["none"])
    return command, result


def close_tls_socket(connection, logger: logging.Logger) -> None:
    status = send_and_collect(connection, logger, "AT+MIPCLOSE?")
    if not status.ok or not socket_is_active(status.raw, SOCKET_ID):
        raise RuntimeError("TLS socket was not active before close")
    result = send_and_collect(
        connection,
        logger,
        f"AT+MIPCLOSE={SOCKET_ID}",
        timeout=15.0,
        completion=mipclose_complete(SOCKET_ID),
        quiet_period=0.75,
    )
    urcs = [line.decode("ascii", errors="replace") for line in result.lines if line.startswith(b"+MIPCLOSE:")]
    logger.info("MIPCLOSE FINAL URC | %s", urcs or ["none"])
    confirm = send_and_collect(connection, logger, "AT+MIPCLOSE?")
    if not confirm.ok or socket_is_active(confirm.raw, SOCKET_ID):
        raise RuntimeError("socket 1 did not close cleanly")
    logger.info("SOCKET CLOSED | socket_id=1 | success=true")


def main() -> int:
    logger, log_path = configure_logging()
    logger.info(
        "L610 TLS RESTORE START | port=%s | baudrate=%d | host=%s | port=%d | log=%s",
        SERIAL_PORT,
        BAUDRATE,
        REMOTE_HOST,
        REMOTE_PORT,
        log_path,
    )
    logger.info("BOUNDARY | SSL restore and one TLS socket probe only; no MIPSEND; no MQTT bytes")

    try:
        with open_serial(SERIAL_PORT, BAUDRATE, COMMAND_TIMEOUT_SECONDS) as connection:
            time.sleep(0.20)
            if not send_and_collect(connection, logger, "AT").ok:
                raise RuntimeError(f"{SERIAL_PORT} did not return OK")
            ensure_data_connection(connection, logger)

            clock = send_and_collect(connection, logger, "AT+CCLK?")
            if not clock.ok or not connection_clock_plausible(clock.raw):
                raise RuntimeError("module clock is unavailable or implausible for certificate validation")

            trust_count, certificate_loaded = ensure_ssl_configuration(connection, logger)
            command, open_result = open_tls_socket(connection, logger)

            # A non-empty TRUSTFILE list is opaque: the query returns a count, not
            # an addressable slot.  Preserve the single accepted repair path from
            # the 2026-08-07 log if an older entry exists but SSL reports -19.
            if not socket_open_succeeded(open_result.raw, SOCKET_ID):
                ssl_error_result = send_and_collect(connection, logger, "AT+GTSSLERR?")
                ssl_error = parse_single_integer(ssl_error_result.raw, b"+GTSSLERR:")
                if ssl_error == -19 and not certificate_loaded:
                    logger.warning(
                        "OPAQUE TRUSTFILE REPAIR | GTSSLERR=-19 | uploading accepted complete PEM once"
                    )
                    certificate_result = load_official_trust_certificate(connection, logger)
                    if not certificate_result.ok:
                        raise RuntimeError("accepted complete PEM TRUSTFILE repair failed")
                    files_confirm = send_and_collect(connection, logger, "AT+GTSSLFILE?")
                    repaired_count = parse_trustfile_count(files_confirm.raw)
                    if repaired_count is None or repaired_count <= trust_count:
                        raise RuntimeError("TRUSTFILE repair count did not increase")
                    trust_count = repaired_count
                    certificate_loaded = True
                    command, open_result = open_tls_socket(connection, logger)
                if not socket_open_succeeded(open_result.raw, SOCKET_ID):
                    raise RuntimeError(
                        f"TLS MIPOPEN failed | command={command} | GTSSLERR={ssl_error}"
                    )

            logger.info(
                "TLS SOCKET ESTABLISHED | socket_id=1 | final_urc=+MIPOPEN: 1,1 | "
                "GTSSLVER=4 | GTSSLMODE=1 | TRUSTFILE_COUNT=%d",
                trust_count,
            )
            read_for_duration(connection, logger, SOCKET_HOLD_SECONDS)
            close_tls_socket(connection, logger)

        logger.info("TLS RESTORE ACCEPTANCE SUCCESS | no MQTT data was sent")
        logger.info("LOG PATH | %s", log_path)
        return 0
    except Exception as exc:
        logger.exception("TLS RESTORE FAILED | %s", exc)
        logger.info("LOG PATH | %s", log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
