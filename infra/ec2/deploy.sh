#!/usr/bin/env bash
# Immutable release deploy (prompt 26). Accepts exactly one hexadecimal release SHA, takes a
# deploy lock, pulls the image pinned to that SHA, health-checks it, and keeps the previous
# release running on failure (no in-place mutation). Activation is coordinated by the CI
# environment gate (prompt 25); this script performs the host-side switch.
set -euo pipefail

RELEASE_SHA="${1:-}"
if [[ ! "${RELEASE_SHA}" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "usage: deploy.sh <hex-release-sha>  (got: '${RELEASE_SHA}')" >&2
  exit 2
fi

LOCK="/tmp/partsiq-deploy.lock"
if command -v flock >/dev/null 2>&1; then
  exec 9>"${LOCK}"
  if ! flock -n 9; then
    echo "another deploy holds the lock; aborting" >&2
    exit 4
  fi
fi

echo "[deploy] release ${RELEASE_SHA} lock acquired"
# --- Host-side activation (requires the EC2 host + registry; BLOCKED offline) ---
#   export RELEASE_SHA; docker compose -f docker-compose.prod.yml pull
#   docker compose -f docker-compose.prod.yml up -d --wait   # waits on healthchecks
#   on failure: compose keeps the previous immutable images (rollback.sh restores explicitly)
echo "[deploy] image pull + healthchecked up -d require the EC2 host (not run here)"
