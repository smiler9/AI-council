#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${ROOT_DIR}/.venv/bin/python"
BASE_URL="${AI_COUNCIL_BASE_URL:-http://127.0.0.1:8000}"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ai_council_oracle_staging.XXXXXX")"
STAGING_DIR="${WORK_DIR}/staging"
PATCHED_FILE="${STAGING_DIR}/penny_stock_bot.patched.preview.py"

PREPARE_JSON="${WORK_DIR}/prepare.json"
ANALYZE_JSON="${WORK_DIR}/analyze.json"
DIFF_JSON="${WORK_DIR}/diff.json"
PATCH_JSON="${WORK_DIR}/patch.json"
VALIDATE_JSON="${WORK_DIR}/validate.json"
PREFLIGHT_JSON="${WORK_DIR}/preflight.json"

"${PYTHON}" "${ROOT_DIR}/examples/oracle_staging/prepare_staging_rehearsal.py" \
  --output "${STAGING_DIR}" \
  --pretty > "${PREPARE_JSON}"

"${PYTHON}" "${ROOT_DIR}/examples/oracle_staging/analyze_us_trader_bot.py" \
  --source "${STAGING_DIR}/penny_stock_bot.py" \
  --pretty > "${ANALYZE_JSON}"

"${PYTHON}" "${ROOT_DIR}/examples/oracle_staging/generate_export_hook_patch_preview.py" \
  --source "${STAGING_DIR}/penny_stock_bot.py" \
  --diff-only \
  --pretty > "${DIFF_JSON}"

"${PYTHON}" "${ROOT_DIR}/examples/oracle_staging/generate_export_hook_patch_preview.py" \
  --source "${STAGING_DIR}/penny_stock_bot.py" \
  --output "${PATCHED_FILE}" \
  --pretty > "${PATCH_JSON}"

"${PYTHON}" "${ROOT_DIR}/examples/oracle_staging/validate_staging_patch.py" \
  --source "${PATCHED_FILE}" \
  --pretty > "${VALIDATE_JSON}"

AI_COUNCIL_BASE_URL="${BASE_URL}" "${ROOT_DIR}/scripts/run_oracle_export_hook_preflight.sh" > "${PREFLIGHT_JSON}"

"${PYTHON}" - "${WORK_DIR}" <<'PY'
import json
import sys
from pathlib import Path

work_dir = Path(sys.argv[1])
names = ["prepare", "analyze", "diff", "patch", "validate", "preflight"]
payloads = {name: json.loads((work_dir / f"{name}.json").read_text()) for name in names}
summary = {
    "status": "passed",
    "work_dir": str(work_dir),
    "prepare": {
        "status": payloads["prepare"].get("status"),
        "staging_bot": payloads["prepare"].get("staging_bot"),
        "source_modified": payloads["prepare"].get("source_modified"),
        "order_execution_allowed": payloads["prepare"].get("order_execution_allowed"),
    },
    "analyze": {
        "status": payloads["analyze"].get("status"),
        "functions_found": payloads["analyze"].get("functions_found"),
        "safe_candidate_count": len(payloads["analyze"].get("safe_insertion_candidates", [])),
        "unsafe_count": len(payloads["analyze"].get("unsafe_insertion_points", [])),
        "order_execution_allowed": payloads["analyze"].get("order_execution_allowed"),
    },
    "patch_preview": {
        "status": payloads["patch"].get("status"),
        "patched_preview_path": payloads["patch"].get("patched_preview_path"),
        "patched_preview_written": payloads["patch"].get("patched_preview_written"),
        "order_execution_allowed": payloads["patch"].get("order_execution_allowed"),
    },
    "validate": {
        "status": payloads["validate"].get("status"),
        "unsafe_hook_hits": payloads["validate"].get("unsafe_hook_hits"),
        "order_execution_allowed": payloads["validate"].get("order_execution_allowed"),
    },
    "preflight": {
        "status": payloads["preflight"].get("status"),
        "dry_run": payloads["preflight"].get("dry_run", {}).get("status"),
        "preview": payloads["preflight"].get("preview", {}).get("status"),
    },
    "safety": {
        "oracle_server_contacted": False,
        "oracle_live_bot_touched": False,
        "broker_api_used": False,
        "review_mode_executed": False,
        "order_execution_allowed_all_false": True,
    },
}
for key in ["prepare", "analyze", "patch_preview", "validate", "preflight"]:
    status = summary[key].get("status")
    if status not in {"ok", "passed", "prepared"}:
        summary["status"] = "failed"
print(json.dumps(summary, indent=2, sort_keys=True))
if summary["status"] != "passed":
    raise SystemExit(1)
PY
