#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_readonly_precheck" / "precheck_result.json"
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
    parser = argparse.ArgumentParser(description="Record a sanitized Oracle read-only precheck result.")
    parser.add_argument("--input", help="Optional JSON result input to sanitize and normalize.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--result-status", choices=["passed", "warning", "failed", "incomplete"], default="passed")
    parser.add_argument("--host", default="<oracle-host>")
    parser.add_argument("--user", default="<oracle-user>")
    parser.add_argument("--trading-dir", default="<oracle-trading-dir>")
    parser.add_argument("--service", action="append", dest="services", default=None)
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


def load_or_build_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.input:
        input_path = Path(args.input).expanduser().resolve()
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input JSON must contain an object")
        return payload
    services = args.services or ["<service-name>:status_observed"]
    return {
        "result_status": args.result_status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "oracle": {
            "host": args.host,
            "user": args.user,
            "trading_dir": args.trading_dir,
        },
        "observations": {
            "hostname_checked": True,
            "trading_dir_exists": True,
            "penny_stock_bot_exists": True,
            "server_py_exists": True,
            "secrets_dir_exists": True,
            "python3_available": True,
            "disk_space_ok": True,
            "services_observed": services,
        },
        "remote_write_executed": False,
        "systemd_changed": False,
        "oracle_live_bot_modified": False,
        "order_execution_allowed": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise ValueError("secret/private key/token marker found in input")
    sanitized = json.loads(json.dumps(payload))
    sanitized.setdefault("result_status", "incomplete")
    sanitized.setdefault("checked_at", datetime.now(timezone.utc).isoformat())
    sanitized.setdefault("oracle", {})
    sanitized["oracle"]["host"] = sanitize_non_secret_identifier(str(sanitized["oracle"].get("host", "<oracle-host>")), "<oracle-host>")
    sanitized["oracle"]["user"] = sanitize_non_secret_identifier(str(sanitized["oracle"].get("user", "<oracle-user>")), "<oracle-user>")
    sanitized["oracle"]["trading_dir"] = sanitize_path(str(sanitized["oracle"].get("trading_dir", "<oracle-trading-dir>")))
    sanitized.setdefault("observations", {})
    sanitized["remote_write_executed"] = False
    sanitized["systemd_changed"] = False
    sanitized["oracle_live_bot_modified"] = False
    sanitized["order_execution_allowed"] = False
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
    return value


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
