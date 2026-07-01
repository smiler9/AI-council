#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

PRECREATION_PLAN="${ROOT_DIR}/tmp/oracle_outbox_precreation/precreation_plan.json"
MANUAL_COMMANDS_DIR="${ROOT_DIR}/tmp/oracle_outbox_precreation/commands"
OUTPUT_DIR="${ROOT_DIR}/tmp/oracle_final_approval"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_final_approval/build_final_approval_packet.py" \
  --precreation-plan "${PRECREATION_PLAN}" \
  --manual-commands-dir "${MANUAL_COMMANDS_DIR}" \
  --output "${OUTPUT_DIR}" \
  --force \
  --pretty
