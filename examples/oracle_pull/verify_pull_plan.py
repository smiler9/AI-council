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
]
ORDER_TRUE_PATTERNS = [
    re.compile(r"order_execution_allowed\s*[:=]\s*true", re.IGNORECASE),
    re.compile(r'"order_execution_allowed"\s*:\s*true', re.IGNORECASE),
    re.compile(r"ORDER_EXECUTION_ALLOWED\s*=\s*true", re.IGNORECASE),
]
DANGEROUS_PATTERNS = [
    re.compile(r"\brm\s+"),
    re.compile(r"\bmv\s+"),
    re.compile(r"\bchmod\s+"),
    re.compile(r"\bchown\s+"),
    re.compile(r"\bmkdir\s+"),
    re.compile(r"\btouch\s+"),
    re.compile(r"\bsystemctl\s+(?:start|stop|restart|reload|enable|disable)\b"),
    re.compile(r"\bngrok\s+(?:http|tcp|start)\b"),
    re.compile(r"\bcloudflared\s+tunnel\s+run\b"),
    re.compile(r"\btailscale\s+up\b"),
    re.compile(r"\bssh\s+-N\s+-R\b"),
    re.compile(r"\bsubmit_order\s*\("),
    re.compile(r"\bcreate_order\s*\("),
    re.compile(r"\bcancel_order\s*\("),
    re.compile(r"\bclose_position\s*\("),
    re.compile(r"\bplace_order\s*\("),
    re.compile(r"\bcheck_exits\s*\("),
    re.compile(r"\bforce_close_all\s*\("),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Mac pull Oracle outbox plan.")
    parser.add_argument("--plan", required=True, help="Pull plan JSON path.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = verify_plan(Path(args.plan))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def verify_plan(path: Path) -> dict[str, Any]:
    plan_path = path.expanduser().resolve()
    if not plan_path.exists():
        return failure(f"plan not found: {plan_path}")
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    errors: list[str] = []

    if payload.get("mode") not in {"preview", "read_only"}:
        errors.append("mode must be preview or read_only")
    if payload.get("strategy") != "mac_pull_oracle_outbox":
        errors.append("strategy must be mac_pull_oracle_outbox")
    if payload.get("remote_delete") is not False:
        errors.append("remote_delete must be false")
    if payload.get("remote_move") is not False:
        errors.append("remote_move must be false")
    if payload.get("manual_approval_required") is not True:
        errors.append("manual_approval_required must be true")
    if payload.get("order_execution_allowed") is not False:
        errors.append("order_execution_allowed must be false")

    secret_hits = pattern_hits(SECRET_PATTERNS, text)
    order_true_hits = pattern_hits(ORDER_TRUE_PATTERNS, text)
    dangerous_hits = pattern_hits(DANGEROUS_PATTERNS, text)
    if secret_hits:
        errors.append("secret/private key/token marker found")
    if order_true_hits:
        errors.append("order_execution_allowed true marker found")
    if dangerous_hits:
        errors.append("dangerous remote write/tunnel/order command marker found")

    return {
        "status": "failed" if errors else "ok",
        "plan_path": str(plan_path),
        "mode": payload.get("mode"),
        "strategy": payload.get("strategy"),
        "secret_hits": secret_hits,
        "order_true_hits": order_true_hits,
        "dangerous_hits": dangerous_hits,
        "errors": errors,
        "remote_delete": False,
        "remote_move": False,
        "order_execution_allowed": False,
    }


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
