#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_outbox_creation_result" / "creation_result_template.json"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an Oracle outbox creation result template.")
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
            "systemd_changed": False,
            "live_bot_modified": False,
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
        "created_at": None,
        "oracle_target": {
            "host": "<oracle-host>",
            "user": "<oracle-user>",
            "trading_dir": "<oracle-trading-dir>",
        },
        "created_paths": {
            "outbox_dir": "<oracle-trading-dir>/ai_council_outbox",
            "processed_dir": "<oracle-trading-dir>/ai_council_processed",
            "failed_dir": "<oracle-trading-dir>/ai_council_failed",
            "state_dir": "<oracle-trading-dir>/ai_council_state",
        },
        "observations": {
            "outbox_dir_exists": False,
            "processed_dir_exists": False,
            "failed_dir_exists": False,
            "state_dir_exists": False,
            "dirs_owned_by_expected_user": False,
            "dirs_readable": False,
            "dirs_writable_by_expected_user": False,
            "disk_space_ok": False,
            "post_creation_verify_readonly_only": True,
        },
        "safety": {
            "systemd_changed": False,
            "live_bot_modified": False,
            "penny_stock_bot_modified": False,
            "secrets_exposed": False,
            "order_execution_allowed": False,
            "broker_api_called": False,
        },
        "notes": [],
        "next_step_requested": "preview_signal_file_write_rehearsal",
        "safety_boundary": SAFETY_BOUNDARY,
    }


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
