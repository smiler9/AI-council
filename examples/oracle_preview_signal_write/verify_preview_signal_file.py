#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = ["source", "signal_id", "symbol", "signal", "action", "price", "volume", "timestamp"]
REQUIRED_TRUE_FIELDS = ["review_only", "simulation_only"]
REQUIRED_FALSE_FIELDS = ["order_execution_allowed"]
ORDER_LIKE_FIELDS = [
    "quantity",
    "qty",
    "shares",
    "order_type",
    "stop_loss",
    "take_profit",
    "broker",
    "account",
    "route",
    "tif",
    "submit_order",
    "place_order",
]
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a local Oracle preview signal JSON file.")
    parser.add_argument("--signal", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = verify_signal(Path(args.signal))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def verify_signal(signal_path: Path) -> dict[str, Any]:
    path = signal_path.expanduser().resolve()
    if not path.exists():
        return failure(f"signal not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return failure(f"invalid JSON: {exc}")
    if not isinstance(payload, dict):
        return failure("signal JSON must be an object")

    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    errors: list[str] = []
    warnings: list[str] = []

    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        errors.append(f"missing required fields: {missing}")
    for field in REQUIRED_TRUE_FIELDS:
        if payload.get(field) is not True:
            errors.append(f"{field} must be true")
    for field in REQUIRED_FALSE_FIELDS:
        if payload.get(field) is not False:
            errors.append(f"{field} must be false")

    order_like_found = [field for field in ORDER_LIKE_FIELDS if field in payload]
    if order_like_found:
        warnings.append(f"order-like fields are review context only: {order_like_found}")

    secret_hits = pattern_hits(SECRET_PATTERNS, text)
    order_true_hits = pattern_hits(ORDER_TRUE_PATTERNS, text)
    if secret_hits:
        errors.append("secret/private key/token/oracle host marker found")
    if order_true_hits:
        errors.append("order_execution_allowed true marker found")

    validation_status = "failed" if errors else ("warning" if warnings else "passed")
    return {
        "status": "ok" if not errors else "failed",
        "validation_status": validation_status,
        "signal_path": str(path),
        "signal_id": payload.get("signal_id"),
        "order_like_fields_found": order_like_found,
        "errors": errors,
        "warnings": warnings,
        "secret_hits": secret_hits,
        "order_true_hits": order_true_hits,
        "review_only": payload.get("review_only") is True,
        "simulation_only": payload.get("simulation_only") is True,
        "order_execution_allowed": False,
    }


def pattern_hits(patterns: list[re.Pattern[str]], text: str) -> list[str]:
    return [pattern.pattern for pattern in patterns if pattern.search(text)]


def failure(message: str) -> dict[str, Any]:
    return {"status": "failed", "validation_status": "failed", "errors": [message], "order_execution_allowed": False}


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
