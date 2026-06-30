#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${AI_COUNCIL_BASE_URL:-http://127.0.0.1:8000}"

"${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/examples/oracle_sidecar/oracle_export_hook_preflight.py" --base-url "${BASE_URL}" --pretty
