#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

INTAKE_PATH="${ROOT_DIR}/tmp/oracle_precheck_intake/precheck_intake.json"
OUTPUT_PATH="${ROOT_DIR}/tmp/oracle_precheck_intake/go_no_go_decision.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_precheck_intake/decide_precreation_go_no_go.py" \
  --intake "${INTAKE_PATH}" \
  --output "${OUTPUT_PATH}" \
  --pretty
