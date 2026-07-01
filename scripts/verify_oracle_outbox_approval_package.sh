#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIR="${ROOT_DIR}/tmp/oracle_outbox_approval"

"${ROOT_DIR}/.venv/bin/python" \
  "${ROOT_DIR}/examples/oracle_outbox_approval/verify_outbox_approval_package.py" \
  --package "${PACKAGE_DIR}" \
  --pretty
