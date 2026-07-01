#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_precheck_intake" / "precheck_intake_template.json"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a manual Oracle precheck intake template.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        payload = build_template()
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        result = {
            "status": "ok",
            "template_path": str(output),
            "result_status": payload["result_status"],
            "remote_write_executed": False,
            "systemd_changed": False,
            "order_execution_allowed": False,
        }
    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "order_execution_allowed": False}
        print_json(result, pretty=args.pretty)
        return 1
    print_json(result, pretty=args.pretty)
    return 0


def build_template() -> dict[str, Any]:
    return {
        "result_status": "incomplete",
        "manual_operator": "<manual-operator>",
        "checked_at": None,
        "oracle_target": {
            "host": "<oracle-host>",
            "user": "<oracle-user>",
            "trading_dir": "<oracle-trading-dir>",
        },
        "observations": {
            "hostname_checked": False,
            "user_checked": False,
            "trading_dir_exists": False,
            "penny_stock_bot_exists": False,
            "server_py_exists": False,
            "secrets_dir_exists": False,
            "python3_available": False,
            "disk_space_ok": False,
            "services_observed": [],
            "active_services": [],
            "process_listing_reviewed": False,
            "crontab_reviewed": False,
            "systemd_status_readonly_only": False,
        },
        "safety": {
            "remote_write_executed": False,
            "systemd_changed": False,
            "live_bot_modified": False,
            "secrets_exposed": False,
            "order_execution_allowed": False,
        },
        "notes": [],
        "next_step_requested": "outbox_precreation_manual_review",
        "safety_boundary": SAFETY_BOUNDARY,
    }


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
