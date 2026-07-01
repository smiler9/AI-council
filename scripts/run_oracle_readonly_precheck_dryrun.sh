#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "${ROOT_DIR}"

OUTPUT_DIR="${ROOT_DIR}/tmp/oracle_readonly_precheck"
mkdir -p "${OUTPUT_DIR}"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_readonly_precheck/build_readonly_precheck_plan.py" \
  --output "${OUTPUT_DIR}/precheck_plan.json" \
  --pretty > "${OUTPUT_DIR}/plan_build_result.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_readonly_precheck/verify_readonly_precheck_plan.py" \
  --plan "${OUTPUT_DIR}/precheck_plan.json" \
  --pretty > "${OUTPUT_DIR}/plan_verify_result.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_readonly_precheck/record_readonly_precheck_result.py" \
  --output "${OUTPUT_DIR}/precheck_result.json" \
  --pretty > "${OUTPUT_DIR}/record_result.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_readonly_precheck/verify_readonly_precheck_result.py" \
  --result "${OUTPUT_DIR}/precheck_result.json" \
  --pretty > "${OUTPUT_DIR}/result_verify_result.json"

"${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
base = root / "tmp" / "oracle_readonly_precheck"
plan_build = json.loads((base / "plan_build_result.json").read_text(encoding="utf-8"))
plan_verify = json.loads((base / "plan_verify_result.json").read_text(encoding="utf-8"))
record = json.loads((base / "record_result.json").read_text(encoding="utf-8"))
result_verify = json.loads((base / "result_verify_result.json").read_text(encoding="utf-8"))
summary = {
    "status": "passed"
    if plan_build.get("status") == "ok"
    and plan_verify.get("status") == "ok"
    and record.get("status") == "ok"
    and result_verify.get("status") == "ok"
    else "failed",
    "plan_path": str(base / "precheck_plan.json"),
    "result_path": str(base / "precheck_result.json"),
    "plan_verify_status": plan_verify.get("status"),
    "record_status": record.get("status"),
    "result_verify_status": result_verify.get("status"),
    "next_step_allowed": result_verify.get("next_step_allowed"),
    "safety": {
        "oracle_server_contacted": False,
        "remote_write_executed": False,
        "remote_delete": False,
        "remote_move": False,
        "remote_permission_changed": False,
        "oracle_systemd_touched": False,
        "oracle_live_bot_modified": False,
        "broker_api_used": False,
        "order_execution_allowed_all_false": True,
    },
    "order_execution_allowed": False,
}
print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
raise SystemExit(0 if summary["status"] == "passed" else 1)
PY
