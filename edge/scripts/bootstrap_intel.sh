#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash edge/scripts/bootstrap_intel.sh [--apply]

Default mode is read-only. --apply creates edge/.venv and installs only
edge/requirements.txt. This script never uses sudo and never changes SSH,
networking, firewall, Tuya settings, or modem state.
EOF
}

apply=false
case "${1:-}" in
  "") ;;
  --apply) apply=true ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
edge_dir="$(CDPATH= cd -- "${script_dir}/.." && pwd)"
repo_dir="$(CDPATH= cd -- "${edge_dir}/.." && pwd)"

printf 'QMZG Intel bootstrap audit\n'
printf 'repo=%s\n' "${repo_dir}"
printf 'kernel=%s\n' "$(uname -srmo)"

if [[ ! -r /etc/os-release ]]; then
  printf 'ERROR: /etc/os-release is not readable\n' >&2
  exit 3
fi
. /etc/os-release
printf 'os=%s\n' "${PRETTY_NAME:-unknown}"

if ! command -v python3 >/dev/null 2>&1; then
  printf 'ERROR: python3 is not installed. Stop and ask the onsite user before installing packages.\n' >&2
  exit 4
fi
printf 'python=%s\n' "$(python3 --version 2>&1)"
printf 'user=%s uid=%s\n' "$(id -un)" "$(id -u)"
printf 'groups=%s\n' "$(id -nG)"

if id -nG | tr ' ' '\n' | grep -Eq '^(dialout|uucp)$'; then
  printf 'serial_group=present\n'
else
  printf 'serial_group=missing (onsite approval may be needed; this script will not run sudo)\n'
fi

if [[ -f "${edge_dir}/.env" ]]; then
  printf 'edge_config=present (values not displayed)\n'
else
  printf 'edge_config=missing; provision securely from edge/.env.example\n'
fi

if [[ "${apply}" != true ]]; then
  printf 'mode=audit-only\n'
  printf 'next=bash edge/scripts/bootstrap_intel.sh --apply\n'
  exit 0
fi

printf 'mode=apply-edge-python-only\n'
python3 -m venv "${edge_dir}/.venv"
"${edge_dir}/.venv/bin/python" -m pip install --upgrade pip
"${edge_dir}/.venv/bin/python" -m pip install -r "${edge_dir}/requirements.txt"
"${edge_dir}/.venv/bin/python" -m pytest "${edge_dir}/tests" -q
printf 'bootstrap=complete\n'
printf 'No hardware command was executed.\n'
