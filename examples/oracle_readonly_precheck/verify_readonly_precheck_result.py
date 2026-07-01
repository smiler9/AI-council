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

REQUIRED_OBSERVATIONS = [
    "hostname_checked",
    "trading_dir_exists",
    "penny_stock_bot_exists",
    "server_py_exists",
    "secrets_dir_exists",
    "python3_available",
    "disk_space_ok",
    "services_observed",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a sanitized Oracle read-only precheck result.")
    parser.add_argument("--result", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = verify_result(Path(args.result))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def verify_result(result_path: Path) -> dict[str, Any]:
    path = result_path.expanduser().resolve()
    if not path.exists():
        return failure(f"result not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("remote_write_executed") is not False:
        errors.append("remote_write_executed must be false")
    if payload.get("systemd_changed") is not False:
        errors.append("systemd_changed must be false")
    if payload.get("order_execution_allowed") is not False:
        errors.append("order_execution_allowed must be false")
    if payload.get("approved") is True:
        warnings.append("approved field is not used by read-only precheck and should not drive next steps")

    observations = payload.get("observations", {})
    missing_observations = [key for key in REQUIRED_OBSERVATIONS if key not in observations]
    false_required = [
        key
        for key in REQUIRED_OBSERVATIONS
        if key in observations and key != "services_observed" and observations.get(key) is not True
    ]
    if missing_observations:
        errors.append(f"missing required observations: {missing_observations}")
    if false_required:
        errors.append(f"required observations are not true: {false_required}")
    if not isinstance(observations.get("services_observed", []), list):
        errors.append("services_observed must be a list")

    secret_hits = pattern_hits(SECRET_PATTERNS, text)
    order_true_hits = pattern_hits(ORDER_TRUE_PATTERNS, text)
    if secret_hits:
        errors.append("secret/private key/token/oracle host marker found")
    if order_true_hits:
        errors.append("order_execution_allowed true marker found")

    result_status = payload.get("result_status")
    next_step_allowed = result_status == "passed" and not errors
    if result_status != "passed":
        warnings.append("result_status is not passed; do not proceed to any write step")

    return {
        "status": "failed" if errors else "ok",
        "result_path": str(path),
        "result_status": result_status,
        "next_step_allowed": next_step_allowed,
        "missing_observations": missing_observations,
        "false_required_observations": false_required,
        "secret_hits": secret_hits,
        "order_true_hits": order_true_hits,
        "warnings": warnings,
        "errors": errors,
        "remote_write_executed": False,
        "systemd_changed": False,
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
