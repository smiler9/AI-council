#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import PurePosixPath, Path
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    re.compile(r"ssh-key-20\d{2}", re.IGNORECASE),
    re.compile(r"/Users/[^\\s'\"]*/\\.ssh/[^\\s'\"]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\b"),
]
ORDER_TRUE_PATTERNS = [
    re.compile(r"order_execution_allowed\s*[:=]\s*true", re.IGNORECASE),
    re.compile(r'"order_execution_allowed"\s*:\s*true', re.IGNORECASE),
    re.compile(r"ORDER_EXECUTION_ALLOWED\s*=\s*true", re.IGNORECASE),
]
ACTIVE_DANGEROUS_PATTERNS = [
    re.compile(r"\brm\s+"),
    re.compile(r"\bmv\s+"),
    re.compile(r"\bchmod\s+"),
    re.compile(r"\bchown\s+"),
    re.compile(r"\bsystemctl\s+(?:start|stop|restart|reload|enable|disable)\b"),
    re.compile(r"\bservice\s+\S+\s+(?:start|stop|restart)\b"),
    re.compile(r"\bsubmit_order\s*\("),
    re.compile(r"\bcreate_order\s*\("),
    re.compile(r"\bcancel_order\s*\("),
    re.compile(r"\bclose_position\s*\("),
]
FORBIDDEN_MODES = {"live", "order", "trading", "live_order", "live_trading", "execute"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an Oracle outbox pre-creation plan.")
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

    if payload.get("mode") != "precreation_manual":
        errors.append("mode must be precreation_manual")
    if str(payload.get("mode", "")).lower() in FORBIDDEN_MODES:
        errors.append("live/order/trading execution mode is not allowed")
    if payload.get("manual_approval_required") is not True:
        errors.append("manual_approval_required must be true")
    if payload.get("remote_write_executed") is not False:
        errors.append("remote_write_executed must be false")
    if payload.get("remote_delete") is not False:
        errors.append("remote_delete must be false")
    if payload.get("remote_move") is not False:
        errors.append("remote_move must be false")
    if payload.get("systemd_changes_planned") is not False:
        errors.append("systemd_changes_planned must be false")
    if payload.get("order_execution_allowed") is not False:
        errors.append("order_execution_allowed must be false")
    if payload.get("oracle_server_contacted") is not False:
        errors.append("oracle_server_contacted must be false")

    path_errors = validate_paths(payload.get("paths", {}))
    errors.extend(path_errors)

    secret_hits = pattern_hits(SECRET_PATTERNS, text)
    order_true_hits = pattern_hits(ORDER_TRUE_PATTERNS, text)
    dangerous_hits = pattern_hits(ACTIVE_DANGEROUS_PATTERNS, text)
    if secret_hits:
        errors.append("secret/private key/token marker found")
    if order_true_hits:
        errors.append("order_execution_allowed true marker found")
    if dangerous_hits:
        errors.append("active remote delete/move/permission/system/order command marker found")
    if "live_order" in text or "live_trading" in text:
        errors.append("live order/trading text is not allowed")

    return {
        "status": "failed" if errors else "ok",
        "plan_path": str(path),
        "mode": payload.get("mode"),
        "secret_hits": secret_hits,
        "order_true_hits": order_true_hits,
        "dangerous_hits": dangerous_hits,
        "path_errors": path_errors,
        "errors": errors,
        "manual_approval_required": payload.get("manual_approval_required") is True,
        "remote_write_executed": False,
        "remote_delete": False,
        "remote_move": False,
        "systemd_changes_planned": False,
        "order_execution_allowed": False,
    }


def validate_paths(paths: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(paths, dict):
        return ["paths must be an object"]
    required = {"trading_dir", "outbox_dir", "processed_dir", "failed_dir", "state_dir", "log_path"}
    missing = sorted(required - set(paths))
    if missing:
        errors.append(f"missing paths: {missing}")
    for key, value in paths.items():
        if not isinstance(value, str) or not value:
            errors.append(f"{key} must be a non-empty string")
            continue
        if "\x00" in value or "\n" in value or "\r" in value:
            errors.append(f"{key} contains invalid control characters")
        if has_path_traversal(value):
            errors.append(f"{key} contains path traversal")
    return errors


def has_path_traversal(value: str) -> bool:
    if value.startswith("<") and value.endswith(">"):
        return False
    return ".." in PurePosixPath(value).parts


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
