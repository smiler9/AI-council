#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="${ORACLE_SIGNAL_EXPORT_BUNDLE_DIR:-${ROOT_DIR}/tmp/oracle_signal_export_bundle}"
PLAN_PATH="${ORACLE_PREVIEW_DEPLOY_PLAN:-${ROOT_DIR}/tmp/oracle_preview_deploy_plan.json}"

if [[ ! -f "${BUNDLE_DIR}/manifest.json" ]]; then
  "${ROOT_DIR}/scripts/build_oracle_signal_export_bundle.sh" >/dev/null
fi

"${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/examples/oracle_preview_deploy/prepare_preview_deploy_plan.py" \
  --bundle "${BUNDLE_DIR}" \
  --output "${PLAN_PATH}" \
  --mode preview \
  --pretty
