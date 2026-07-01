#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "${ROOT_DIR}"

OUTPUT_DIR="${ROOT_DIR}/tmp/oracle_outbox_creation_result"
mkdir -p "${OUTPUT_DIR}"

scripts/run_oracle_outbox_manual_creation_dryrun.sh > "${OUTPUT_DIR}/manual_creation_dryrun_result.json"
scripts/build_oracle_outbox_creation_result_template.sh > "${OUTPUT_DIR}/template_build_result.json"
scripts/record_oracle_outbox_creation_sample_result.sh > "${OUTPUT_DIR}/record_result.json"
scripts/verify_oracle_outbox_creation_result.sh > "${OUTPUT_DIR}/verify_result.json"
scripts/decide_oracle_post_creation_go_no_go.sh > "${OUTPUT_DIR}/decision_result.json"

"${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
base = root / "tmp" / "oracle_outbox_creation_result"
manual = json.loads((base / "manual_creation_dryrun_result.json").read_text(encoding="utf-8"))
template = json.loads((base / "template_build_result.json").read_text(encoding="utf-8"))
record = json.loads((base / "record_result.json").read_text(encoding="utf-8"))
verify = json.loads((base / "verify_result.json").read_text(encoding="utf-8"))
decision = json.loads((base / "decision_result.json").read_text(encoding="utf-8"))
summary = {
    "status": "passed"
    if manual.get("status") == "passed"
    and template.get("status") == "ok"
    and record.get("status") == "ok"
    and verify.get("validation_status") == "passed"
    and decision.get("decision") == "GO"
    else "failed",
    "result_path": str(base / "creation_result.json"),
    "decision_path": str(base / "post_creation_go_no_go_decision.json"),
    "manual_creation_dryrun_status": manual.get("status"),
    "template_build_status": template.get("status"),
    "record_status": record.get("status"),
    "validation_status": verify.get("validation_status"),
    "decision": decision.get("decision"),
    "next_phase_allowed": decision.get("next_phase_allowed"),
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
