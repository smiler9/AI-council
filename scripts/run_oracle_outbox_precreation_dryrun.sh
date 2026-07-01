#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

OUTPUT_DIR="${ROOT_DIR}/tmp/oracle_outbox_precreation"
BUILD_RESULT="${OUTPUT_DIR}/build_result.json"
VERIFY_RESULT="${OUTPUT_DIR}/verify_result.json"
COMMAND_RESULT="${OUTPUT_DIR}/command_result.json"

mkdir -p "${OUTPUT_DIR}"
cd "${ROOT_DIR}"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_precreation/build_outbox_precreation_plan.py" \
  --output "${OUTPUT_DIR}/precreation_plan.json" \
  --pretty > "${BUILD_RESULT}"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_precreation/verify_outbox_precreation_plan.py" \
  --plan "${OUTPUT_DIR}/precreation_plan.json" \
  --pretty > "${VERIFY_RESULT}"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_precreation/generate_manual_precreation_commands.py" \
  --plan "${OUTPUT_DIR}/precreation_plan.json" \
  --output "${OUTPUT_DIR}/commands" \
  --pretty > "${COMMAND_RESULT}"

"${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
base = root / "tmp" / "oracle_outbox_precreation"
build = json.loads((base / "build_result.json").read_text(encoding="utf-8"))
verify = json.loads((base / "verify_result.json").read_text(encoding="utf-8"))
commands = json.loads((base / "command_result.json").read_text(encoding="utf-8"))
summary = {
    "status": "passed" if build.get("status") == verify.get("status") == commands.get("status") == "ok" else "failed",
    "plan_path": str(base / "precreation_plan.json"),
    "command_dir": str(base / "commands"),
    "command_file_count": commands.get("command_file_count"),
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
