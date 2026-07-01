#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_creation_result/verify_creation_result.py" \
  --result "${ROOT_DIR}/tmp/oracle_outbox_creation_result/creation_result.json" \
  --pretty
