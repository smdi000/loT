#!/usr/bin/env bash
set -euo pipefail

backend_dir="/opt/qmzg/backend"
compose_file="${backend_dir}/docker-compose.prod.yml"
env_file="${backend_dir}/.env"
container_name="backend-postgres-1"

cd "${backend_dir}"
test -f "${env_file}"
docker inspect "${container_name}" >/dev/null

new_password="$(openssl rand -hex 32)"

# The local PostgreSQL socket accepts the container's postgres OS user without
# exposing a password. Send the ALTER ROLE statement through stdin so the new
# secret is not present in process arguments or logs.
printf "ALTER ROLE qmzg WITH PASSWORD '%s';\n" "${new_password}" \
    | docker exec -i "${container_name}" psql -U qmzg -d qmzg >/dev/null

umask 077
while IFS= read -r line || [ -n "${line}" ]; do
    case "${line}" in
        POSTGRES_PASSWORD=*)
            printf 'POSTGRES_PASSWORD=%s\n' "${new_password}"
            ;;
        *)
            printf '%s\n' "${line}"
            ;;
    esac
done < "${env_file}" > "${env_file}.new"

mv "${env_file}.new" "${env_file}"
chmod 600 "${env_file}"

docker compose --env-file "${env_file}" -f "${compose_file}" \
    up -d --force-recreate postgres >/dev/null

for _ in $(seq 1 40); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "${container_name}" 2>/dev/null || true)"
    if [ "${status}" = "healthy" ]; then
        echo "PostgreSQL password rotated and container environment aligned."
        exit 0
    fi
    sleep 2
done

echo "PostgreSQL did not become healthy after password rotation." >&2
exit 1
