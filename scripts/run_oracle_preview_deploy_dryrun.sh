#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${ROOT_DIR}/tmp"
PLAN_JSON="${WORK_DIR}/oracle_preview_deploy_plan.json"
PREPARE_JSON="${WORK_DIR}/oracle_preview_deploy_prepare.json"
VERIFY_JSON="${WORK_DIR}/oracle_preview_deploy_verify.json"
COMMANDS_JSON="${WORK_DIR}/oracle_preview_commands.json"
BUNDLE_JSON="${WORK_DIR}/oracle_signal_export_bundle_build.json"
BUNDLE_VERIFY_JSON="${WORK_DIR}/oracle_signal_export_bundle_verify.json"
READINESS_JSON="${WORK_DIR}/oracle_readiness_dryrun.json"

mkdir -p "${WORK_DIR}"

"${ROOT_DIR}/scripts/build_oracle_signal_export_bundle.sh" > "${BUNDLE_JSON}"
"${ROOT_DIR}/scripts/verify_oracle_signal_export_bundle.sh" > "${BUNDLE_VERIFY_JSON}"
"${ROOT_DIR}/scripts/run_oracle_readiness_check_dryrun.sh" > "${READINESS_JSON}"
"${ROOT_DIR}/scripts/prepare_oracle_preview_deploy_plan.sh" > "${PREPARE_JSON}"
"${ROOT_DIR}/scripts/verify_oracle_preview_deploy_plan.sh" > "${VERIFY_JSON}"
"${ROOT_DIR}/scripts/generate_oracle_preview_commands.sh" > "${COMMANDS_JSON}"

"${ROOT_DIR}/.venv/bin/python" - "${WORK_DIR}" <<'PY'
import json
import sys
from pathlib import Path

work = Path(sys.argv[1])
payloads = {
    "bundle_build": json.loads((work / "oracle_signal_export_bundle_build.json").read_text()),
    "bundle_verify": json.loads((work / "oracle_signal_export_bundle_verify.json").read_text()),
    "readiness": json.loads((work / "oracle_readiness_dryrun.json").read_text()),
    "plan_prepare": json.loads((work / "oracle_preview_deploy_prepare.json").read_text()),
    "plan": json.loads((work / "oracle_preview_deploy_plan.json").read_text()),
    "plan_verify": json.loads((work / "oracle_preview_deploy_verify.json").read_text()),
    "commands": json.loads((work / "oracle_preview_commands.json").read_text()),
}
summary = {
    "status": "passed",
    "bundle_build": {
        "status": payloads["bundle_build"].get("status"),
        "bundle_path": payloads["bundle_build"].get("bundle_path"),
        "order_execution_allowed": payloads["bundle_build"].get("order_execution_allowed"),
    },
    "bundle_verify": {
        "status": payloads["bundle_verify"].get("status"),
        "secret_hits": payloads["bundle_verify"].get("secret_hits"),
        "dangerous_hits": payloads["bundle_verify"].get("dangerous_hits"),
        "order_execution_allowed": payloads["bundle_verify"].get("order_execution_allowed"),
    },
    "readiness": {
        "status": payloads["readiness"].get("status"),
        "mode": payloads["readiness"].get("mode"),
        "ssh_executed": payloads["readiness"].get("ssh_executed"),
        "oracle_server_contacted": payloads["readiness"].get("oracle_server_contacted"),
        "order_execution_allowed": payloads["readiness"].get("order_execution_allowed"),
    },
    "plan": {
        "status": payloads["plan_prepare"].get("status"),
        "plan_path": payloads["plan_prepare"].get("plan_path"),
        "mode": payloads["plan"].get("mode"),
        "manual_approval_required": payloads["plan_prepare"].get("manual_approval_required"),
        "order_execution_allowed": payloads["plan"].get("order_execution_allowed"),
    },
    "plan_verify": {
        "status": payloads["plan_verify"].get("status"),
        "errors": payloads["plan_verify"].get("errors"),
        "order_execution_allowed": payloads["plan_verify"].get("order_execution_allowed"),
    },
    "commands": {
        "status": payloads["commands"].get("status"),
        "output_dir": payloads["commands"].get("output_dir"),
        "command_file_count": payloads["commands"].get("command_file_count"),
        "order_execution_allowed": payloads["commands"].get("order_execution_allowed"),
    },
    "safety": {
        "oracle_server_contacted": False,
        "oracle_files_written": False,
        "oracle_systemd_touched": False,
        "oracle_live_bot_modified": False,
        "broker_api_used": False,
        "order_execution_allowed_all_false": True,
    },
}
for name, payload in payloads.items():
    status = payload.get("status")
    if status not in {"ok", "passed"}:
        summary["status"] = "failed"
        summary.setdefault("failed_steps", []).append(name)
print(json.dumps(summary, indent=2, sort_keys=True))
if summary["status"] != "passed":
    raise SystemExit(1)
PY
