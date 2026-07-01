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
    "hostname_checked",
    "user_checked",
    "trading_dir_exists",
    "penny_stock_bot_exists",
    "server_py_exists",
    "secrets_dir_exists",
    "python3_available",
    "disk_space_ok",
    "process_listing_reviewed",
    "crontab_reviewed",
    "systemd_status_readonly_only",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a manual Oracle precheck intake JSON.")
    parser.add_argument("--intake", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = validate_intake(Path(args.intake))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def validate_intake(intake_path: Path) -> dict[str, Any]:
    path = intake_path.expanduser().resolve()
    if not path.exists():
        return failure(f"intake not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    errors: list[str] = []
    warnings: list[str] = []

    result_status = payload.get("result_status")
    if result_status not in VALID_RESULT_STATUSES:
        errors.append("result_status must be passed, warning, failed, or incomplete")
    if result_status in {"warning", "incomplete"}:
        warnings.append(f"result_status is {result_status}; manual review is required")
    if result_status == "failed":
        errors.append("result_status is failed")

    observations = payload.get("observations", {})
    safety = payload.get("safety", {})
    if not isinstance(observations, dict):
        errors.append("observations must be an object")
        observations = {}
    if not isinstance(safety, dict):
        errors.append("safety must be an object")
        safety = {}

    failed_safety = []
    for key in ["remote_write_executed", "systemd_changed", "live_bot_modified", "secrets_exposed", "order_execution_allowed"]:
        if safety.get(key) is not False:
            failed_safety.append(key)
    if failed_safety:
        errors.append(f"safety flags must be false: {failed_safety}")

    false_required = [key for key in REQUIRED_TRUE_OBSERVATIONS if observations.get(key) is not True]
    if false_required:
        errors.append(f"required observations are not true: {false_required}")
    if not isinstance(observations.get("services_observed"), list) or not observations.get("services_observed"):
        errors.append("services_observed must be a non-empty list")
    if not isinstance(observations.get("active_services"), list) or not observations.get("active_services"):
        warnings.append("active_services is empty; confirm whether services were observed")

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
        "intake_path": str(path),
        "result_status": result_status,
        "errors": errors,
        "warnings": warnings,
        "secret_hits": secret_hits,
        "order_true_hits": order_true_hits,
        "required_observations_checked": REQUIRED_TRUE_OBSERVATIONS,
        "remote_write_executed": False,
        "systemd_changed": False,
        "live_bot_modified": False,
        "secrets_exposed": False,
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
