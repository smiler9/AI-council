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
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
]
ORDER_TRUE_PATTERNS = [
    re.compile(r"order_execution_allowed\s*[:=]\s*true", re.IGNORECASE),
    re.compile(r'"order_execution_allowed"\s*:\s*true', re.IGNORECASE),
]
FORBIDDEN_ACTIVE_PATTERNS = [
    re.compile(r"^\s*mkdir\b"),
    re.compile(r"^\s*touch\b"),
    re.compile(r"^\s*cp\b"),
    re.compile(r"^\s*mv\b"),
    re.compile(r"^\s*rm\b"),
    re.compile(r"^\s*chmod\b"),
    re.compile(r"^\s*chown\b"),
    re.compile(r"^\s*systemctl\s+(?:start|stop|restart|reload|enable|disable)\b"),
    re.compile(r"^\s*docker\s+(?:start|stop|restart)\b"),
    re.compile(r"\bpython(?:3)?\s+penny_stock_bot\.py\b"),
    re.compile(r"^\s*cat\s+.*(?:\.secrets|\.env|token|secret|kis_config)", re.IGNORECASE),
    re.compile(r"\bplace_order\b"),
    re.compile(r"\bsubmit_order\b"),
    re.compile(r"\bcreate_order\b"),
    re.compile(r"\bcancel_order\b"),
    re.compile(r"\bclose_position\b"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an Oracle read-only precheck plan.")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--pretty", action="store_true")
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

    if payload.get("mode") != "readonly_precheck":
        errors.append("mode must be readonly_precheck")
    if payload.get("manual_execution_required") is not True:
        errors.append("manual_execution_required must be true")
    if payload.get("remote_write_allowed") is not False:
        errors.append("remote_write_allowed must be false")
    if payload.get("remote_write_executed") is not False:
        errors.append("remote_write_executed must be false")
    if payload.get("systemd_changes_allowed") is not False:
        errors.append("systemd_changes_allowed must be false")
    if payload.get("order_execution_allowed") is not False:
        errors.append("order_execution_allowed must be false")

    secret_hits = pattern_hits(SECRET_PATTERNS, text)
    order_true_hits = pattern_hits(ORDER_TRUE_PATTERNS, text)
    active_forbidden_hits = command_hits(payload.get("commands", []))
    if secret_hits:
        errors.append("secret/private key/token/oracle host marker found")
    if order_true_hits:
        errors.append("order_execution_allowed true marker found")
    if active_forbidden_hits:
        errors.append("forbidden active command found")

    categories = {item.get("category") for item in payload.get("commands", []) if isinstance(item, dict)}
    required_categories = {
        "identity",
        "system_info",
        "disk",
        "python_env",
        "trading_dir_exists",
        "service_status_readonly",
        "process_listing",
        "crontab_readonly",
    }
    missing_categories = sorted(required_categories - categories)
    if missing_categories:
        errors.append(f"missing command categories: {missing_categories}")

    return {
        "status": "failed" if errors else "ok",
        "plan_path": str(path),
        "command_count": len(payload.get("commands", [])),
        "missing_categories": missing_categories,
        "secret_hits": secret_hits,
        "order_true_hits": order_true_hits,
        "active_forbidden_hits": active_forbidden_hits,
        "errors": errors,
        "remote_write_allowed": False,
        "remote_write_executed": False,
        "systemd_changes_allowed": False,
        "order_execution_allowed": False,
    }


def command_hits(commands: Any) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if not isinstance(commands, list):
        return [{"index": -1, "command": "<invalid commands>", "pattern": "commands must be a list"}]
    for index, item in enumerate(commands):
        if not isinstance(item, dict):
            hits.append({"index": index, "command": str(item), "pattern": "command item must be an object"})
            continue
        shell = str(item.get("command", ""))
        for pattern in FORBIDDEN_ACTIVE_PATTERNS:
            if pattern.search(shell):
                hits.append({"index": index, "command": shell, "pattern": pattern.pattern})
    return hits


def pattern_hits(patterns: list[re.Pattern[str]], text: str) -> list[str]:
    return [pattern.pattern for pattern in patterns if pattern.search(text)]


def failure(message: str) -> dict[str, Any]:
    return {"status": "failed", "errors": [message], "order_execution_allowed": False}


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
