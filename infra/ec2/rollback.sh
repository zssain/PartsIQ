#!/usr/bin/env bash
# Rollback (prompt 26). Re-activates the PREVIOUS immutable release SHA (a schema-compatible
# image), never resetting the database. Publication history and audit are retained.
set -euo pipefail

PREVIOUS_SHA="${1:-}"
if [[ ! "${PREVIOUS_SHA}" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "usage: rollback.sh <previous-hex-release-sha>  (got: '${PREVIOUS_SHA}')" >&2
  exit 2
fi
echo "[rollback] re-activating previous release ${PREVIOUS_SHA}"
# --- Host-side rollback (requires the EC2 host; BLOCKED offline) ---
#   export RELEASE_SHA="${PREVIOUS_SHA}"; docker compose -f docker-compose.prod.yml up -d --wait
#   applied SQL is NEVER reset; a compensating migration + backup review handles schema changes
echo "[rollback] compose re-activation requires the EC2 host (not run here)"
