#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ORACLE_SIGNAL_EXPORT_BUNDLE_DIR:-${ROOT_DIR}/tmp/oracle_signal_export_bundle}"

"${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/examples/oracle_deployment/build_signal_export_bundle.py" \
  --output "${OUTPUT_DIR}" \
  --force \
  --pretty
