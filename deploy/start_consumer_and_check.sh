#!/usr/bin/env bash
set -euo pipefail

cd /opt/qmzg/backend
compose=(docker compose --env-file .env -f docker-compose.prod.yml)
access_id="$(sed -n 's/^TUYA_ACCESS_ID=//p' .env | tail -n 1)"
started_at="$(date --iso-8601=seconds)"

"${compose[@]}" up -d tuya-consumer >/dev/null

connected=0
for _ in $(seq 1 45); do
    if "${compose[@]}" logs --since "${started_at}" tuya-consumer 2>&1 \
        | grep -F 'Tuya Pulsar connected' >/dev/null; then
        connected=1
        break
    fi
    sleep 2
done

raw_log="$(mktemp /tmp/qmzg-consumer-start.XXXXXX)"
trap 'rm -f "${raw_log}"' EXIT
"${compose[@]}" logs --since "${started_at}" --tail=80 tuya-consumer \
    >"${raw_log}" 2>&1 || true
sed "s/${access_id}/<masked-access-id>/g" "${raw_log}"

if [ "${connected}" -ne 1 ]; then
    echo "CONSUMER_CONNECTION=failed"
    exit 1
fi

echo "CONSUMER_CONNECTION=connected"
"${compose[@]}" ps tuya-consumer
