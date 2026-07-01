#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

PLAN_PATH="${ROOT_DIR}/tmp/oracle_outbox_precreation/precreation_plan.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_precreation/verify_outbox_precreation_plan.py" \
  --plan "${PLAN_PATH}" \
  --pretty
