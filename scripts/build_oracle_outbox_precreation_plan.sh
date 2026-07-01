#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

OUTPUT_PATH="${ROOT_DIR}/tmp/oracle_outbox_precreation/precreation_plan.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_precreation/build_outbox_precreation_plan.py" \
  --output "${OUTPUT_PATH}" \
  --pretty
