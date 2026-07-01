#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "${ROOT_DIR}"

OUTPUT_DIR="${ROOT_DIR}/tmp/oracle_outbox_manual_creation"

PRECREATION_RESULT="$(mktemp)"
PRECHECK_RESULT="$(mktemp)"
BUILD_RESULT="$(mktemp)"

scripts/run_oracle_outbox_precreation_dryrun.sh > "${PRECREATION_RESULT}"
scripts/run_oracle_precheck_intake_dryrun.sh > "${PRECHECK_RESULT}"

scripts/build_oracle_outbox_manual_creation_packet.sh > "${BUILD_RESULT}"
"${PYTHON_BIN}" - "${PRECREATION_RESULT}" "${PRECHECK_RESULT}" "${BUILD_RESULT}" "${OUTPUT_DIR}" <<'PY'
from pathlib import Path
import sys

precreation, precheck, build, output = [Path(value) for value in sys.argv[1:]]
output.mkdir(parents=True, exist_ok=True)
(output / "precreation_dryrun_result.json").write_text(precreation.read_text(encoding="utf-8"), encoding="utf-8")
(output / "precheck_intake_dryrun_result.json").write_text(precheck.read_text(encoding="utf-8"), encoding="utf-8")
(output / "packet_build_result.json").write_text(build.read_text(encoding="utf-8"), encoding="utf-8")
PY
scripts/review_oracle_outbox_creation_commands.sh > "${OUTPUT_DIR}/command_review_result.json"
scripts/verify_oracle_outbox_manual_creation_packet.sh > "${OUTPUT_DIR}/packet_verify_result.json"

"${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
base = root / "tmp" / "oracle_outbox_manual_creation"
precreation = json.loads((base / "precreation_dryrun_result.json").read_text(encoding="utf-8"))
precheck = json.loads((base / "precheck_intake_dryrun_result.json").read_text(encoding="utf-8"))
build = json.loads((base / "packet_build_result.json").read_text(encoding="utf-8"))
review = json.loads((base / "command_review_result.json").read_text(encoding="utf-8"))
verify = json.loads((base / "packet_verify_result.json").read_text(encoding="utf-8"))
summary = {
    "status": "passed"
    if precreation.get("status") == "passed"
    and precheck.get("status") == "passed"
    and build.get("status") == "ok"
    and review.get("status") == "passed"
    and verify.get("status") == "ok"
    else "failed",
    "packet_path": str(base),
    "precreation_dryrun_status": precreation.get("status"),
    "precheck_intake_status": precheck.get("status"),
    "packet_build_status": build.get("status"),
    "command_review_status": review.get("status"),
    "packet_verify_status": verify.get("status"),
    "creation_executed": False,
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
