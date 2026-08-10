#!/usr/bin/env bash
set -euo pipefail

cd /opt/qmzg/backend
compose=(docker compose --env-file .env -f docker-compose.prod.yml)
access_id="$(sed -n 's/^TUYA_ACCESS_ID=//p' .env | tail -n 1)"
raw_log="$(mktemp /tmp/qmzg-pulsar-diag.XXXXXX)"

cleanup() {
    rm -f "${raw_log}"
    "${compose[@]}" up -d tuya-consumer >/dev/null 2>&1 || true
}
trap cleanup EXIT

"${compose[@]}" stop tuya-consumer >/dev/null

set +e
"${compose[@]}" run --rm --no-deps \
    -v /opt/qmzg/deploy/pulsar_connect_diagnostic.py:/tmp/pulsar_connect_diagnostic.py:ro \
    tuya-consumer python /tmp/pulsar_connect_diagnostic.py >"${raw_log}" 2>&1
result=$?
set -e

# Pulsar debug logs contain the Access ID inside topic names. Redact it before
# displaying diagnostics; the Access Secret is never logged by the script.
sed "s/${access_id}/<masked-access-id>/g" "${raw_log}"
exit "${result}"
