#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "${ROOT_DIR}"

OUTPUT_DIR="${ROOT_DIR}/tmp/oracle_preview_signal_write"
mkdir -p "${OUTPUT_DIR}"

scripts/run_oracle_outbox_creation_result_dryrun.sh > "${OUTPUT_DIR}/outbox_creation_result_dryrun.json"
scripts/build_oracle_preview_signal_file.sh > "${OUTPUT_DIR}/signal_build_result.json"
scripts/verify_oracle_preview_signal_file.sh > "${OUTPUT_DIR}/signal_verify_result.json"
scripts/build_oracle_preview_signal_write_packet.sh > "${OUTPUT_DIR}/packet_build_result.json"
scripts/verify_oracle_preview_signal_write_packet.sh > "${OUTPUT_DIR}/packet_verify_result.json"
scripts/record_oracle_preview_signal_write_sample_result.sh > "${OUTPUT_DIR}/record_result.json"
scripts/verify_oracle_preview_signal_write_result.sh > "${OUTPUT_DIR}/verify_result.json"
scripts/decide_oracle_pull_rehearsal_go_no_go.sh > "${OUTPUT_DIR}/decision_result.json"

"${PYTHON_BIN}" - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
base = root / "tmp" / "oracle_preview_signal_write"
outbox = json.loads((base / "outbox_creation_result_dryrun.json").read_text(encoding="utf-8"))
signal_build = json.loads((base / "signal_build_result.json").read_text(encoding="utf-8"))
signal_verify = json.loads((base / "signal_verify_result.json").read_text(encoding="utf-8"))
packet_build = json.loads((base / "packet_build_result.json").read_text(encoding="utf-8"))
packet_verify = json.loads((base / "packet_verify_result.json").read_text(encoding="utf-8"))
record = json.loads((base / "record_result.json").read_text(encoding="utf-8"))
verify = json.loads((base / "verify_result.json").read_text(encoding="utf-8"))
decision = json.loads((base / "decision_result.json").read_text(encoding="utf-8"))
summary = {
    "status": "passed"
    if outbox.get("status") == "passed"
    and signal_build.get("status") == "ok"
    and signal_verify.get("validation_status") == "passed"
    and packet_build.get("status") == "ok"
    and packet_verify.get("status") == "ok"
    and record.get("status") == "ok"
    and verify.get("validation_status") == "passed"
    and decision.get("decision") == "GO"
    else "failed",
    "signal_path": str(base / "us_trader_preview_signal.json"),
    "packet_path": str(base / "manual_write_packet"),
    "result_path": str(base / "signal_write_result.json"),
    "decision_path": str(base / "pull_rehearsal_go_no_go_decision.json"),
    "outbox_creation_result_dryrun_status": outbox.get("status"),
    "signal_build_status": signal_build.get("status"),
    "signal_validation_status": signal_verify.get("validation_status"),
    "packet_build_status": packet_build.get("status"),
    "packet_verify_status": packet_verify.get("status"),
    "record_status": record.get("status"),
    "write_result_validation_status": verify.get("validation_status"),
    "decision": decision.get("decision"),
    "next_phase_allowed": decision.get("next_phase_allowed"),
    "safety": {
        "oracle_server_contacted": False,
        "remote_write_executed": False,
        "remote_upload_executed": False,
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
