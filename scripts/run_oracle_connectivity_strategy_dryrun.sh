#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${ROOT_DIR}/tmp"
COMPARE_JSON="${WORK_DIR}/oracle_connectivity_compare.json"
GENERATE_JSON="${WORK_DIR}/oracle_connectivity_generate.json"
VERIFY_JSON="${WORK_DIR}/oracle_connectivity_verify.json"
PLAN_JSON="${WORK_DIR}/oracle_connectivity_plan.json"

mkdir -p "${WORK_DIR}"

"${ROOT_DIR}/scripts/compare_oracle_connectivity_options.sh" > "${COMPARE_JSON}"
"${ROOT_DIR}/scripts/generate_oracle_connectivity_plan.sh" > "${GENERATE_JSON}"
"${ROOT_DIR}/scripts/verify_oracle_connectivity_plan.sh" > "${VERIFY_JSON}"

"${ROOT_DIR}/.venv/bin/python" - "${WORK_DIR}" <<'PY'
import json
import sys
from pathlib import Path

work = Path(sys.argv[1])
payloads = {
    "compare": json.loads((work / "oracle_connectivity_compare.json").read_text()),
    "generate": json.loads((work / "oracle_connectivity_generate.json").read_text()),
    "verify": json.loads((work / "oracle_connectivity_verify.json").read_text()),
    "plan": json.loads((work / "oracle_connectivity_plan.json").read_text()),
}
summary = {
    "status": "passed",
    "compare": {
        "status": payloads["compare"].get("status"),
        "recommended_option": payloads["compare"].get("recommended_option"),
        "network_changes_performed": payloads["compare"].get("network_changes_performed"),
        "order_execution_allowed": payloads["compare"].get("order_execution_allowed"),
    },
    "generate": {
        "status": payloads["generate"].get("status"),
        "option": payloads["generate"].get("option"),
        "mode": payloads["generate"].get("mode"),
        "order_execution_allowed": payloads["generate"].get("order_execution_allowed"),
    },
    "verify": {
        "status": payloads["verify"].get("status"),
        "secret_hits": payloads["verify"].get("secret_hits"),
        "dangerous_hits": payloads["verify"].get("dangerous_hits"),
        "order_execution_allowed": payloads["verify"].get("order_execution_allowed"),
    },
    "plan": {
        "option": payloads["plan"].get("option"),
        "mode": payloads["plan"].get("mode"),
        "risk_level": payloads["plan"].get("risk_level"),
        "network_changes_performed": payloads["plan"].get("network_changes_performed"),
        "tunnel_started": payloads["plan"].get("tunnel_started"),
        "ssh_executed": payloads["plan"].get("ssh_executed"),
        "order_execution_allowed": payloads["plan"].get("order_execution_allowed"),
    },
    "safety": {
        "network_changes_performed": False,
        "tunnel_started": False,
        "ssh_executed": False,
        "oracle_live_bot_modified": False,
        "oracle_systemd_touched": False,
        "broker_api_used": False,
        "order_execution_allowed_all_false": True,
    },
}
for name in ["compare", "generate", "verify"]:
    if payloads[name].get("status") != "ok":
        summary["status"] = "failed"
        summary.setdefault("failed_steps", []).append(name)
print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
if summary["status"] != "passed":
    raise SystemExit(1)
PY
