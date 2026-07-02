#!/usr/bin/env bash
# Long-running Oracle preview operations loop for launchd/screen supervision.
# Preview-only: read-only Oracle pull, trade review, paper simulation.
# No broker orders; order_execution_allowed=false is enforced downstream.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ORACLE_PREVIEW_LOOP_ENV:-$ROOT_DIR/tmp/oracle_operations/oracle_preview_loop.env}"
INTERVAL="${ORACLE_PREVIEW_LOOP_INTERVAL_SECONDS:-60}"

cd "$ROOT_DIR"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

while true; do
  date -u +"--- %Y-%m-%dT%H:%M:%SZ preview loop run ---"
  scripts/run_oracle_preview_operations_once.sh --pretty || true
  sleep "$INTERVAL"
done
