#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BASE_URL="${AI_COUNCIL_BASE_URL:-http://127.0.0.1:8000}"

if ! curl -fsS "${BASE_URL}/health" >/dev/null; then
  echo "AI Council backend is not reachable at ${BASE_URL}."
  echo "Start it first: scripts/run_backend.sh"
  exit 1
fi

cd "$ROOT_DIR"
python3 examples/integration/run_diagnostics.py --base-url "$BASE_URL" --pretty
