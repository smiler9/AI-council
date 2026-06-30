#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAN_PATH="${ORACLE_PREVIEW_DEPLOY_PLAN:-${ROOT_DIR}/tmp/oracle_preview_deploy_plan.json}"

if [[ ! -f "${PLAN_PATH}" ]]; then
  "${ROOT_DIR}/scripts/prepare_oracle_preview_deploy_plan.sh" >/dev/null
fi

"${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/examples/oracle_preview_deploy/verify_preview_deploy_plan.py" \
  --plan "${PLAN_PATH}" \
  --pretty
