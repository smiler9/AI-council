#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "${ROOT_DIR}"
"${PYTHON_BIN}" examples/oracle_preview_signal_write/decide_pull_rehearsal_go_no_go.py \
  --result tmp/oracle_preview_signal_write/signal_write_result.json \
  --output tmp/oracle_preview_signal_write/pull_rehearsal_go_no_go_decision.json
