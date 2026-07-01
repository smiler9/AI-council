#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "${ROOT_DIR}"
"${PYTHON_BIN}" examples/oracle_preview_signal_write/build_preview_signal_file.py \
  --output tmp/oracle_preview_signal_write/us_trader_preview_signal.json
