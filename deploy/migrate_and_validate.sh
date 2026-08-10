#!/usr/bin/env bash
set -euo pipefail

cd /opt/qmzg/backend
compose=(docker compose --env-file .env -f docker-compose.prod.yml)

"${compose[@]}" run --rm api alembic upgrade head

revision="$("${compose[@]}" exec -T postgres \
    psql -U qmzg -d qmzg -tAc 'SELECT version_num FROM alembic_version')"

tables="$("${compose[@]}" exec -T postgres \
    psql -U qmzg -d qmzg -tAc \
    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")"

echo "ALEMBIC_REVISION=${revision}"
echo "TABLES"
printf '%s\n' "${tables}"

test "${revision}" = "20260808_02"
for table in alembic_version devices training_sessions tuya_messages user_devices users; do
    printf '%s\n' "${tables}" | grep -Fx "${table}" >/dev/null
done

echo "MIGRATION_VALIDATION_OK"
