#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

MANUAL_COMMANDS_DIR="${ROOT_DIR}/tmp/oracle_outbox_precreation/commands"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_final_approval/review_manual_commands.py" \
  --commands-dir "${MANUAL_COMMANDS_DIR}" \
  --pretty
