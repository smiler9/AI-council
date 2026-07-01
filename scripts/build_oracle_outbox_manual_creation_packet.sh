#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_manual_creation/build_manual_creation_packet.py" \
  --precreation-plan "${ROOT_DIR}/tmp/oracle_outbox_precreation/precreation_plan.json" \
  --go-no-go-decision "${ROOT_DIR}/tmp/oracle_precheck_intake/go_no_go_decision.json" \
  --output "${ROOT_DIR}/tmp/oracle_outbox_manual_creation" \
  --force \
  --pretty
