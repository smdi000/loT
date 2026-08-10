#!/usr/bin/env bash
set -euo pipefail

backend_dir="/opt/qmzg/backend"
source_env="${backend_dir}/.env.source"
target_env="${backend_dir}/.env"

cd "${backend_dir}"
test -f "${source_env}"
chmod 600 "${source_env}"
sed -i 's/\r$//' "${source_env}"

read_env_value() {
    local key="$1"
    sed -n "s/^${key}=//p" "${source_env}" | tail -n 1
}

tuya_access_id="$(read_env_value TUYA_ACCESS_ID)"
tuya_access_secret="$(read_env_value TUYA_ACCESS_SECRET)"
tuya_subscription="$(read_env_value TUYA_PULSAR_SUBSCRIPTION)"

test -n "${tuya_access_id}"
test -n "${tuya_access_secret}"

postgres_password="$(openssl rand -hex 32)"
jwt_secret="$(openssl rand -hex 48)"

umask 077
{
    printf '%s\n' \
        'POSTGRES_DB=qmzg' \
        'POSTGRES_USER=qmzg'
    printf 'POSTGRES_PASSWORD=%s\n' "${postgres_password}"
    printf 'JWT_SECRET=%s\n' "${jwt_secret}"
    printf '%s\n' \
        'JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60' \
        "TUYA_ACCESS_ID=${tuya_access_id}" \
        "TUYA_ACCESS_SECRET=${tuya_access_secret}" \
        'TUYA_PULSAR_URL=pulsar+ssl://mqe.tuyacn.com:7285/' \
        'TUYA_PULSAR_TOPIC=TEST' \
        "TUYA_PULSAR_SUBSCRIPTION=${tuya_subscription}"
} > "${target_env}.new"

mv "${target_env}.new" "${target_env}"
chmod 600 "${target_env}"
rm -f "${source_env}"

find app alembic -type d -exec chmod 750 {} +
find app alembic -type f -exec chmod 640 {} +
chmod 640 alembic.ini Dockerfile requirements.txt docker-compose.prod.yml .dockerignore

echo "Remote production environment generated."
echo "Secret values were not displayed."
