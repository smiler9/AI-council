#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

PACKET_DIR="${ROOT_DIR}/tmp/oracle_final_approval"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_final_approval/verify_final_approval_packet.py" \
  --packet "${PACKET_DIR}" \
  --pretty
