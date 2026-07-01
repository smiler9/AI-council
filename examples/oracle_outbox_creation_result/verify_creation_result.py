#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


VALID_RESULT_STATUSES = {"passed", "warning", "failed", "incomplete"}
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
REQUIRED_TRUE_OBSERVATIONS = [
    "outbox_dir_exists",
    "processed_dir_exists",
    "failed_dir_exists",
    "state_dir_exists",
    "dirs_readable",
    "dirs_writable_by_expected_user",
    "disk_space_ok",
    "post_creation_verify_readonly_only",
]
WARNING_OBSERVATIONS = ["dirs_owned_by_expected_user"]
REQUIRED_FALSE_SAFETY = [
    "systemd_changed",
    "live_bot_modified",
    "penny_stock_bot_modified",
    "secrets_exposed",
    "broker_api_called",
    "order_execution_allowed",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an Oracle outbox creation result JSON.")
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

    result_status = payload.get("result_status")
    if result_status not in VALID_RESULT_STATUSES:
        errors.append("result_status must be passed, warning, failed, or incomplete")
    if result_status == "failed":
        errors.append("result_status is failed")
    if result_status in {"warning", "incomplete"}:
        warnings.append(f"result_status is {result_status}; manual review is required")

    observations = payload.get("observations", {})
    safety = payload.get("safety", {})
    if not isinstance(observations, dict):
        errors.append("observations must be an object")
        observations = {}
    if not isinstance(safety, dict):
        errors.append("safety must be an object")
        safety = {}

    false_required = [key for key in REQUIRED_TRUE_OBSERVATIONS if observations.get(key) is not True]
    if false_required:
        errors.append(f"required observations are not true: {false_required}")
    false_warning = [key for key in WARNING_OBSERVATIONS if observations.get(key) is not True]
    if false_warning:
        warnings.append(f"warning observations are not true: {false_warning}")

    failed_safety = [key for key in REQUIRED_FALSE_SAFETY if safety.get(key) is not False]
    if failed_safety:
        errors.append(f"safety flags must be false: {failed_safety}")

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
        "result_path": str(path),
        "result_status": result_status,
        "errors": errors,
        "warnings": warnings,
        "secret_hits": secret_hits,
        "order_true_hits": order_true_hits,
        "required_observations_checked": REQUIRED_TRUE_OBSERVATIONS,
        "systemd_changed": False,
        "live_bot_modified": False,
        "penny_stock_bot_modified": False,
        "secrets_exposed": False,
        "broker_api_called": False,
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
