#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_creation_result/build_creation_result_template.py" \
  --output "${ROOT_DIR}/tmp/oracle_outbox_creation_result/creation_result_template.json" \
  --pretty
