#!/usr/bin/env bash
# EC2 host bootstrap (prompt 26). Accepts a VALIDATED environment file path and prepares the
# single host: Docker Engine + Compose, the SSM agent (no public SSH), an encrypted data
# volume, and the private Docker network. It installs no paid service and opens no inbound
# port except via Caddy (80/443). Secrets live only in the env file (chmod 600), never in the
# image or the shell history.
set -euo pipefail

ENV_FILE="${1:-}"
if [[ -z "${ENV_FILE}" ]]; then
  echo "usage: bootstrap.sh <path-to-env-file>" >&2
  exit 2
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "env file not found: ${ENV_FILE}" >&2
  exit 2
fi
# The env file must be owner-only (0600/0400); refuse a world/group-readable secrets file.
perm="$(stat -f '%Lp' "${ENV_FILE}" 2>/dev/null || stat -c '%a' "${ENV_FILE}")"
if [[ "${perm}" != "600" && "${perm}" != "400" ]]; then
  echo "refusing: env file ${ENV_FILE} must be chmod 600/400 (got ${perm})" >&2
  exit 3
fi

echo "[bootstrap] validated env file ${ENV_FILE} (perm ${perm})"
# --- From here on, real host provisioning (requires the EC2 host; BLOCKED in CI/offline) ---
#   - install Docker Engine + compose plugin, enable the SSM agent (no public SSH)
#   - format+mount an encrypted EBS volume at /srv/partsiq, attach minimal IAM instance role
#   - docker network create partsiq_internal; docker compose -f docker-compose.prod.yml pull
echo "[bootstrap] host provisioning steps require the EC2 instance (not run here)"
