#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

OUTPUT_PATH="${ROOT_DIR}/tmp/oracle_precheck_intake/precheck_intake_template.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_precheck_intake/build_precheck_intake_template.py" \
  --output "${OUTPUT_PATH}" \
  --pretty
