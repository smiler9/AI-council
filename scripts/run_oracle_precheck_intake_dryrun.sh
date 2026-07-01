#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "${ROOT_DIR}"

OUTPUT_DIR="${ROOT_DIR}/tmp/oracle_precheck_intake"
mkdir -p "${OUTPUT_DIR}"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_precheck_intake/build_precheck_intake_template.py" \
  --output "${OUTPUT_DIR}/precheck_intake_template.json" \
  --pretty > "${OUTPUT_DIR}/template_build_result.json"

"${PYTHON_BIN}" - <<'PY'
from pathlib import Path

root = Path.cwd()
source = root / "examples" / "oracle_precheck_intake" / "sample_precheck_intake.json"
target = root / "tmp" / "oracle_precheck_intake" / "precheck_intake.json"
target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
PY

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_precheck_intake/validate_precheck_intake.py" \
  --intake "${OUTPUT_DIR}/precheck_intake.json" \
  --pretty > "${OUTPUT_DIR}/validation_result.json"

"${PYTHON_BIN}" "${ROOT_DIR}/examples/oracle_precheck_intake/decide_precreation_go_no_go.py" \
  --intake "${OUTPUT_DIR}/precheck_intake.json" \
  --output "${OUTPUT_DIR}/go_no_go_decision.json" \
  --pretty > "${OUTPUT_DIR}/decision_result.json"

"${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
base = root / "tmp" / "oracle_precheck_intake"
template = json.loads((base / "template_build_result.json").read_text(encoding="utf-8"))
validation = json.loads((base / "validation_result.json").read_text(encoding="utf-8"))
decision = json.loads((base / "decision_result.json").read_text(encoding="utf-8"))
summary = {
    "status": "passed"
    if template.get("status") == "ok"
    and validation.get("validation_status") == "passed"
    and decision.get("decision") == "GO"
    else "failed",
    "template_path": str(base / "precheck_intake_template.json"),
    "intake_path": str(base / "precheck_intake.json"),
    "decision_path": str(base / "go_no_go_decision.json"),
    "validation_status": validation.get("validation_status"),
    "decision": decision.get("decision"),
    "next_phase_allowed": decision.get("next_phase_allowed"),
    "decision_scope": "GO allows only the next manual review stage, not deployment or order execution.",
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
