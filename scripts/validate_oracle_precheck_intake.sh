#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

INTAKE_PATH="${ROOT_DIR}/tmp/oracle_precheck_intake/precheck_intake.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_precheck_intake/validate_precheck_intake.py" \
  --intake "${INTAKE_PATH}" \
  --pretty
