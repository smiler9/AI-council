#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${ROOT_DIR}/tmp"
BUILD_JSON="${WORK_DIR}/oracle_outbox_approval_build.json"
VERIFY_JSON="${WORK_DIR}/oracle_outbox_approval_verify.json"
PACKAGE_DIR="${WORK_DIR}/oracle_outbox_approval"

mkdir -p "${WORK_DIR}"

"${ROOT_DIR}/scripts/build_oracle_outbox_approval_package.sh" > "${BUILD_JSON}"
"${ROOT_DIR}/scripts/verify_oracle_outbox_approval_package.sh" > "${VERIFY_JSON}"

"${ROOT_DIR}/.venv/bin/python" - "${BUILD_JSON}" "${VERIFY_JSON}" "${PACKAGE_DIR}" <<'PY'
import json
import sys
from pathlib import Path

build = json.loads(Path(sys.argv[1]).read_text())
verify = json.loads(Path(sys.argv[2]).read_text())
package = Path(sys.argv[3])
summary = {
    "status": "passed",
    "build": {
        "status": build.get("status"),
        "package_path": build.get("package_path"),
        "file_count": build.get("file_count"),
        "manual_approval_required": build.get("manual_approval_required"),
        "remote_delete": build.get("remote_delete"),
        "remote_move": build.get("remote_move"),
        "order_execution_allowed": build.get("order_execution_allowed"),
    },
    "verify": {
        "status": verify.get("status"),
        "secret_hits": verify.get("secret_hits"),
        "active_dangerous_hits": verify.get("active_dangerous_hits"),
        "remote_delete": verify.get("remote_delete"),
        "remote_move": verify.get("remote_move"),
        "order_execution_allowed": verify.get("order_execution_allowed"),
    },
    "package": {
        "exists": package.exists(),
        "manifest_exists": (package / "manifest.json").exists(),
    },
    "safety": {
        "oracle_server_contacted": False,
        "oracle_live_bot_modified": False,
        "oracle_systemd_touched": False,
        "remote_delete_performed": False,
        "remote_move_performed": False,
        "remote_permission_changed": False,
        "broker_api_used": False,
        "order_execution_allowed_all_false": True,
    },
}
for name, payload in {"build": build, "verify": verify}.items():
    if payload.get("status") not in {"ok"}:
        summary["status"] = "failed"
        summary.setdefault("failed_steps", []).append(name)
print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
if summary["status"] != "passed":
    raise SystemExit(1)
PY
