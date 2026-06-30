#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    re.compile(r"ssh-key-20\d{2}", re.IGNORECASE),
    re.compile(r"/Users/[^\\s'\"]*/\\.ssh/[^\\s'\"]+"),
    re.compile(r"\b168\.110\.101\.18\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
]

ORDER_TRUE_PATTERNS = [
    re.compile(r"order_execution_allowed\s*[:=]\s*true", re.IGNORECASE),
    re.compile(r'"order_execution_allowed"\s*:\s*true', re.IGNORECASE),
    re.compile(r"ORDER_EXECUTION_ALLOWED\s*=\s*true", re.IGNORECASE),
]

DANGEROUS_COMMAND_PATTERNS = [
    re.compile(r"\bsystemctl\s+(?:start|stop|restart|enable|disable)\b"),
    re.compile(r"\bservice\s+\S+\s+(?:start|stop|restart)\b"),
    re.compile(r"\bpython(?:3)?\s+penny_stock_bot\.py\b"),
    re.compile(r"\bsubmit_order\s*\("),
    re.compile(r"\bcreate_order\s*\("),
    re.compile(r"\bcancel_order\s*\("),
    re.compile(r"\bclose_position\s*\("),
    re.compile(r"\bplace_order\s*\("),
    re.compile(r"\bcheck_exits\s*\("),
    re.compile(r"\bforce_close_all\s*\("),
]

FORBIDDEN_MODES = {"review", "live", "order", "trade", "execute"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a preview-only Oracle sidecar deployment plan.")
    parser.add_argument("--plan", required=True, help="Preview deploy plan JSON path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    result = verify_plan(Path(args.plan))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def verify_plan(plan_path: Path) -> dict[str, Any]:
    path = plan_path.expanduser().resolve()
    if not path.exists():
        return failure(f"plan not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    errors: list[str] = []

    if payload.get("mode") != "preview":
        errors.append("plan mode must be preview")
    if str(payload.get("mode", "")).lower() in FORBIDDEN_MODES:
        errors.append("plan mode must not be review/live/order/trade/execute")
    if payload.get("order_execution_allowed") is not False:
        errors.append("order_execution_allowed must be false")
    if payload.get("manual_approval_required") is not True:
        errors.append("manual_approval_required must be true")
    if payload.get("auto_start") is not False:
        errors.append("auto_start must be false")
    if payload.get("systemd_enabled") is not False:
        errors.append("systemd_enabled must be false")
    if payload.get("oracle_server_contacted") is not False:
        errors.append("oracle_server_contacted must be false")
    if payload.get("oracle_files_written") is not False:
        errors.append("oracle_files_written must be false")
    if payload.get("oracle_systemd_touched") is not False:
        errors.append("oracle_systemd_touched must be false")
    run_once = str(payload.get("run_once_command_preview", ""))
    if "--mode preview" not in run_once:
        errors.append("run_once_command_preview must explicitly use --mode preview")
    if any(f"--mode {mode}" in run_once for mode in FORBIDDEN_MODES):
        errors.append("run_once_command_preview must not use review/live/order mode")

    secret_hits = pattern_hits(SECRET_PATTERNS, text)
    order_true_hits = pattern_hits(ORDER_TRUE_PATTERNS, text)
    dangerous_hits = pattern_hits(DANGEROUS_COMMAND_PATTERNS, text)
    if secret_hits:
        errors.append("secret/private key/Oracle identity marker found")
    if order_true_hits:
        errors.append("order_execution_allowed=true marker found")
    if dangerous_hits:
        errors.append("dangerous order/system command marker found")

    return {
        "status": "failed" if errors else "ok",
        "plan_path": str(path),
        "mode": payload.get("mode"),
        "manual_approval_required": payload.get("manual_approval_required"),
        "auto_start": payload.get("auto_start"),
        "systemd_enabled": payload.get("systemd_enabled"),
        "secret_hits": secret_hits,
        "order_true_hits": order_true_hits,
        "dangerous_hits": dangerous_hits,
        "errors": errors,
        "oracle_server_contacted": False,
        "oracle_files_written": False,
        "oracle_systemd_touched": False,
        "order_execution_allowed": False,
    }


def pattern_hits(patterns: list[re.Pattern[str]], text: str) -> list[str]:
    return [pattern.pattern for pattern in patterns if pattern.search(text)]


def failure(message: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "errors": [message],
        "order_execution_allowed": False,
    }


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
