#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_outbox_precreation" / "precreation_plan.json"
DEFAULT_TRADING_DIR = "<oracle-trading-dir>"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a placeholder Oracle outbox pre-creation plan.")
    parser.add_argument("--oracle-trading-dir", default=DEFAULT_TRADING_DIR)
    parser.add_argument("--outbox-dir", default=None)
    parser.add_argument("--processed-dir", default=None)
    parser.add_argument("--failed-dir", default=None)
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--log-path", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        plan = build_plan(args)
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        result = {
            "status": "ok",
            "plan_path": str(output),
            "mode": plan["mode"],
            "manual_approval_required": True,
            "remote_write_planned": True,
            "remote_write_executed": False,
            "remote_delete": False,
            "remote_move": False,
            "order_execution_allowed": False,
        }
    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "order_execution_allowed": False}
        print_json(result, pretty=args.pretty)
        return 1

    print_json(result, pretty=args.pretty)
    return 0


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    trading_dir = args.oracle_trading_dir.rstrip("/")
    paths = {
        "trading_dir": trading_dir,
        "outbox_dir": args.outbox_dir or f"{trading_dir}/ai_council_outbox",
        "processed_dir": args.processed_dir or f"{trading_dir}/ai_council_processed",
        "failed_dir": args.failed_dir or f"{trading_dir}/ai_council_failed",
        "state_dir": args.state_dir or f"{trading_dir}/ai_council_state",
        "log_path": args.log_path or f"{trading_dir}/logs/ai_council_export.log",
    }
    return {
        "status": "ok",
        "mode": "precreation_manual",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manual_approval_required": True,
        "remote_write_planned": True,
        "remote_write_executed": False,
        "remote_delete": False,
        "remote_move": False,
        "remote_permission_change_executed": False,
        "systemd_changes_planned": False,
        "oracle_server_contacted": False,
        "oracle_live_bot_modified": False,
        "penny_stock_bot_modified": False,
        "paths": paths,
        "approval_gates": [
            "Review outbox path approval package.",
            "Confirm sidecar and Mac pull smoke tests have passed.",
            "Confirm no export hook has been applied yet.",
            "Confirm no production systemd service will be changed.",
        ],
        "rollback_notes": [
            "Before creation, rollback means stopping the manual approval process.",
            "After a future manual creation, preserve outbox files and stop Mac pull first.",
            "Do not delete remote outbox data automatically.",
        ],
        "simulation_only": True,
        "order_execution_allowed": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
