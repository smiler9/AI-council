#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_creation_result/record_creation_result.py" \
  --input "${ROOT_DIR}/examples/oracle_outbox_creation_result/sample_creation_result_passed.json" \
  --output "${ROOT_DIR}/tmp/oracle_outbox_creation_result/creation_result.json" \
  --pretty
