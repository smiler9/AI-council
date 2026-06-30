#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${AI_COUNCIL_BASE_URL:-http://127.0.0.1:8000}"

if ! curl -fsS "${BASE_URL}/health" >/dev/null; then
  echo "AI Council backend is not reachable at ${BASE_URL}."
  echo "Start the backend first, then re-run this smoke test."
  exit 1
fi

"${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/examples/integration/run_oracle_sidecar_smoke.py" --base-url "${BASE_URL}" --pretty
