#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/tmp/oracle_outbox_approval"

"${ROOT_DIR}/.venv/bin/python" \
  "${ROOT_DIR}/examples/oracle_outbox_approval/build_outbox_approval_package.py" \
  --output "${OUTPUT_DIR}" \
  --force \
  --pretty
