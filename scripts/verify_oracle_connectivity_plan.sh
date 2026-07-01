#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAN_PATH="${ORACLE_CONNECTIVITY_PLAN:-${ROOT_DIR}/tmp/oracle_connectivity_plan.json}"

if [[ ! -f "${PLAN_PATH}" ]]; then
  "${ROOT_DIR}/scripts/generate_oracle_connectivity_plan.sh" >/dev/null
fi

"${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/examples/oracle_connectivity/verify_connectivity_plan.py" \
  --plan "${PLAN_PATH}" \
  --pretty
