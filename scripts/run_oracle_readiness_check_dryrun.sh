#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/examples/oracle_deployment/oracle_readiness_check.py" \
  --dry-run \
  --pretty
