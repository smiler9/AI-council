#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_outbox_creation_result" / "creation_result.json"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)
SECRET_PATTERNS = [
    re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    re.compile(r"ssh-key-20\d{2}", re.IGNORECASE),
    re.compile(r"/Users/[^\\s'\"]*/\\.ssh/[^\\s'\"]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\b"),
]
IP_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a sanitized Oracle outbox creation result.")
    parser.add_argument("--input", help="Optional JSON creation result input to sanitize and normalize.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--result-status", choices=["passed", "warning", "failed", "incomplete"], default="passed")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        payload = load_or_build_payload(args)
        sanitized = sanitize_payload(payload)
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(sanitized, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        result = {
            "status": "ok",
            "result_path": str(output),
            "result_status": sanitized["result_status"],
            "systemd_changed": sanitized["safety"]["systemd_changed"],
            "live_bot_modified": sanitized["safety"]["live_bot_modified"],
            "penny_stock_bot_modified": sanitized["safety"]["penny_stock_bot_modified"],
            "broker_api_called": sanitized["safety"]["broker_api_called"],
            "order_execution_allowed": False,
        }
        if any(
            sanitized["safety"].get(key) is True
            for key in ["systemd_changed", "live_bot_modified", "penny_stock_bot_modified", "secrets_exposed", "broker_api_called"]
        ):
            result["status"] = "warning" if sanitized["result_status"] != "failed" else "failed"
    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "order_execution_allowed": False}
        print_json(result, pretty=args.pretty)
        return 1

    print_json(result, pretty=args.pretty)
    return 0 if result["status"] in {"ok", "warning"} else 1


def load_or_build_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.input:
        input_path = Path(args.input).expanduser().resolve()
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input JSON must contain an object")
        return payload
    return sample_result(result_status=args.result_status)


def sample_result(*, result_status: str) -> dict[str, Any]:
    return {
        "result_status": result_status,
        "manual_operator": "<manual-operator>",
        "created_at": datetime.now(timezone.utc).isoformat(),
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
            "outbox_dir_exists": True,
            "processed_dir_exists": True,
            "failed_dir_exists": True,
            "state_dir_exists": True,
            "dirs_owned_by_expected_user": True,
            "dirs_readable": True,
            "dirs_writable_by_expected_user": True,
            "disk_space_ok": True,
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
        "notes": ["Sample local result only. Do not store secret values."],
        "next_step_requested": "preview_signal_file_write_rehearsal",
        "safety_boundary": SAFETY_BOUNDARY,
    }


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise ValueError("secret/private key/token marker found in input")
    sanitized = json.loads(json.dumps(payload))
    sanitized.setdefault("result_status", "incomplete")
    sanitized.setdefault("manual_operator", "<manual-operator>")
    sanitized.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    sanitized.setdefault("oracle_target", {})
    sanitized["oracle_target"]["host"] = sanitize_non_secret_identifier(
        str(sanitized["oracle_target"].get("host", "<oracle-host>")), "<oracle-host>"
    )
    sanitized["oracle_target"]["user"] = sanitize_non_secret_identifier(
        str(sanitized["oracle_target"].get("user", "<oracle-user>")), "<oracle-user>"
    )
    sanitized["oracle_target"]["trading_dir"] = sanitize_path(
        str(sanitized["oracle_target"].get("trading_dir", "<oracle-trading-dir>"))
    )
    sanitized.setdefault("created_paths", {})
    for key, default in {
        "outbox_dir": "<oracle-trading-dir>/ai_council_outbox",
        "processed_dir": "<oracle-trading-dir>/ai_council_processed",
        "failed_dir": "<oracle-trading-dir>/ai_council_failed",
        "state_dir": "<oracle-trading-dir>/ai_council_state",
    }.items():
        sanitized["created_paths"][key] = sanitize_path(str(sanitized["created_paths"].get(key, default)))
    sanitized.setdefault("observations", {})
    sanitized.setdefault("safety", {})
    for key in ["systemd_changed", "live_bot_modified", "penny_stock_bot_modified", "secrets_exposed", "broker_api_called"]:
        sanitized["safety"][key] = bool(sanitized["safety"].get(key, False))
    sanitized["safety"]["order_execution_allowed"] = False
    sanitized.setdefault("notes", [])
    sanitized["next_step_requested"] = "preview_signal_file_write_rehearsal"
    sanitized["safety_boundary"] = SAFETY_BOUNDARY
    return sanitized


def sanitize_non_secret_identifier(value: str, placeholder: str) -> str:
    if value.startswith("<") and value.endswith(">"):
        return value
    if IP_PATTERN.search(value):
        return placeholder
    return value


def sanitize_path(value: str) -> str:
    if value.startswith("<") and value.endswith(">"):
        return value
    if "/.ssh/" in value or value.startswith("/Users/"):
        return "<redacted-path>"
    if IP_PATTERN.search(value):
        return "<redacted-path>"
    return value


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
