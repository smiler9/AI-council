#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "${ROOT_DIR}"

PACKET_DIR="${ROOT_DIR}/tmp/oracle_final_approval"
RUN_DIR="${ROOT_DIR}/tmp/oracle_final_approval_run"
mkdir -p "${RUN_DIR}"

PRECREATION_PLAN="${RUN_DIR}/precreation_plan.json"
PRECREATION_COMMANDS_DIR="${RUN_DIR}/precreation_commands"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_precreation/build_outbox_precreation_plan.py" \
  --output "${PRECREATION_PLAN}" \
  --pretty > "${RUN_DIR}/precreation_build_result.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_precreation/verify_outbox_precreation_plan.py" \
  --plan "${PRECREATION_PLAN}" \
  --pretty > "${RUN_DIR}/precreation_verify_result.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_outbox_precreation/generate_manual_precreation_commands.py" \
  --plan "${PRECREATION_PLAN}" \
  --output "${PRECREATION_COMMANDS_DIR}" \
  --pretty > "${RUN_DIR}/precreation_commands_result.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_final_approval/review_manual_commands.py" \
  --commands-dir "${PRECREATION_COMMANDS_DIR}" \
  --pretty > "${RUN_DIR}/manual_command_review_result.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_final_approval/build_final_approval_packet.py" \
  --precreation-plan "${PRECREATION_PLAN}" \
  --manual-commands-dir "${PRECREATION_COMMANDS_DIR}" \
  --output "${PACKET_DIR}" \
  --force \
  --pretty > "${RUN_DIR}/build_result.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_final_approval/verify_final_approval_packet.py" \
  --packet "${PACKET_DIR}" \
  --pretty > "${RUN_DIR}/verify_result.json"

"${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
base = root / "tmp" / "oracle_final_approval_run"
packet = root / "tmp" / "oracle_final_approval"
precreation_build = json.loads((base / "precreation_build_result.json").read_text(encoding="utf-8"))
precreation_verify = json.loads((base / "precreation_verify_result.json").read_text(encoding="utf-8"))
precreation_commands = json.loads((base / "precreation_commands_result.json").read_text(encoding="utf-8"))
review = json.loads((base / "manual_command_review_result.json").read_text(encoding="utf-8"))
build = json.loads((base / "build_result.json").read_text(encoding="utf-8"))
verify = json.loads((base / "verify_result.json").read_text(encoding="utf-8"))
summary = {
    "status": "passed"
    if precreation_build.get("status") == "ok"
    and precreation_verify.get("status") == "ok"
    and precreation_commands.get("status") == "ok"
    and review.get("status") == "passed"
    and build.get("status") == "ok"
    and verify.get("status") == "ok"
    else "failed",
    "packet_path": str(packet),
    "manual_command_review_status": review.get("status"),
    "packet_verify_status": verify.get("status"),
    "approval_record_default": {
        "approved": False,
        "order_execution_allowed": False,
    },
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
