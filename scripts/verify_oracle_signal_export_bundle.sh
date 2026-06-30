#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="${ORACLE_SIGNAL_EXPORT_BUNDLE_DIR:-${ROOT_DIR}/tmp/oracle_signal_export_bundle}"

if [[ ! -f "${BUNDLE_DIR}/manifest.json" ]]; then
  "${ROOT_DIR}/scripts/build_oracle_signal_export_bundle.sh" >/dev/null
fi

"${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/examples/oracle_deployment/verify_signal_export_bundle.py" \
  --bundle "${BUNDLE_DIR}" \
  --pretty
