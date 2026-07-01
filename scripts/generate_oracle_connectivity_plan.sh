#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAN_PATH="${ORACLE_CONNECTIVITY_PLAN:-${ROOT_DIR}/tmp/oracle_connectivity_plan.json}"
OPTION="${ORACLE_CONNECTIVITY_OPTION:-oracle_outbox_only_preview}"

"${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/examples/oracle_connectivity/generate_connectivity_plan.py" \
  --option "${OPTION}" \
  --output "${PLAN_PATH}" \
  --pretty
