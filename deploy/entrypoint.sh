#!/bin/bash
# Container entrypoint: restore the SQLite DB from GCS (Litestream), replicate continuously, run the server.
set -euo pipefail
mkdir -p "$(dirname "$GEAP_DB_PATH")" "$GEAP_RUNS_DIR" "$GEAP_WORK_ROOT"
if [ -n "${GEAP_ARTIFACT_BUCKET:-}" ]; then
  export GEAP_DB_REPLICA_URL="gs://${GEAP_ARTIFACT_BUCKET}/db"
  litestream restore -config /app/deploy/litestream.yml -if-db-not-exists -if-replica-exists "$GEAP_DB_PATH" || true
  # model availability probe (a few cents) only when no persisted copy exists
  ( geap-eval preflight --if-missing >/tmp/preflight.log 2>&1 || true ) &
  exec litestream replicate -config /app/deploy/litestream.yml -exec "geap-eval serve"
fi
exec geap-eval serve
