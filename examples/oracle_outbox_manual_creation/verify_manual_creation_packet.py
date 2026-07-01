#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MANUAL_DIR = ROOT / "examples" / "oracle_outbox_manual_creation"
DEFAULT_PACKET = ROOT / "tmp" / "oracle_outbox_manual_creation"
REQUIRED_FILES = {
    "manual_creation_commands.example.sh",
    "post_creation_verify_commands.example.sh",
    "creation_result_record.example.json",
    "rollback_after_creation.example.sh",
    "manual_creation_checklist.md",
    "creation_command_review.json",
}
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
    re.compile(r"ORDER_EXECUTION_ALLOWED\s*=\s*true", re.IGNORECASE),
]
BROKER_ORDER_PATTERNS = [
    re.compile(r"\bpython(?:3)?\s+penny_stock_bot\.py\b"),
    re.compile(r"\bplace_order\s*\("),
    re.compile(r"\bsubmit_order\s*\("),
    re.compile(r"\bcreate_order\s*\("),
    re.compile(r"\bcancel_order\s*\("),
    re.compile(r"\bclose_position\s*\("),
    re.compile(r"\bmarket_order\s*\("),
    re.compile(r"\blimit_order\s*\("),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a local Oracle outbox manual creation command packet.")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = verify_packet(Path(args.packet))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def verify_packet(packet_dir: Path) -> dict[str, Any]:
    packet = packet_dir.expanduser().resolve()
    manifest_path = packet / "manifest.json"
    errors: list[str] = []
    if not packet.exists():
        return failure(f"packet directory not found: {packet}")
    if not manifest_path.exists():
        return failure(f"manifest.json not found in packet: {packet}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_files = {item["path"]: item for item in manifest.get("files", [])}
    missing_required = sorted(REQUIRED_FILES - set(manifest_files))
    if missing_required:
        errors.append(f"missing required manifest entries: {missing_required}")

    hash_failures = []
    for relative, entry in manifest_files.items():
        path = packet / relative
        if not path.exists():
            errors.append(f"manifest file missing: {relative}")
            continue
        expected = entry.get("sha256")
        actual = sha256_file(path)
        if expected != actual:
            hash_failures.append({"path": relative, "expected": expected, "actual": actual})
    if hash_failures:
        errors.append("sha256 verification failed")

    scan_results = scan_packet(packet)
    if scan_results["secret_hits"]:
        errors.append("secret/private key/token/oracle host marker found")
    if scan_results["order_true_hits"]:
        errors.append("order_execution_allowed true marker found")
    if scan_results["broker_order_hits"]:
        errors.append("broker/order execution marker found")

    command_review = run_command_review(packet)
    if command_review.get("status") != "passed":
        errors.append("creation command review must pass")
    if command_review.get("active_dangerous_commands_found") is not False:
        errors.append("active dangerous command must not exist")

    creation_record = load_json(packet / "creation_result_record.example.json", errors)
    if manifest.get("manual_approval_required") is not True:
        errors.append("manifest manual_approval_required must be true")
    if manifest.get("go_is_not_deployment_approval") is not True:
        errors.append("manifest must state GO is not deployment approval")
    if manifest.get("creation_executed") is not False:
        errors.append("manifest creation_executed must be false")
    if manifest.get("remote_write_executed") is not False:
        errors.append("manifest remote_write_executed must be false")
    if manifest.get("systemd_changed") is not False:
        errors.append("manifest systemd_changed must be false")
    if manifest.get("oracle_live_bot_modified") is not False:
        errors.append("manifest oracle_live_bot_modified must be false")
    if manifest.get("order_execution_allowed") is not False:
        errors.append("manifest order_execution_allowed must be false")
    if creation_record:
        if creation_record.get("creation_executed") is not False:
            errors.append("creation_result_record creation_executed must default to false")
        if creation_record.get("remote_write_executed") is not False:
            errors.append("creation_result_record remote_write_executed must be false")
        if creation_record.get("systemd_changed") is not False:
            errors.append("creation_result_record systemd_changed must be false")
        if creation_record.get("live_bot_modified") is not False:
            errors.append("creation_result_record live_bot_modified must be false")
        if creation_record.get("order_execution_allowed") is not False:
            errors.append("creation_result_record order_execution_allowed must be false")
        if creation_record.get("result_status") != "incomplete":
            errors.append("creation_result_record result_status must default to incomplete")

    return {
        "status": "failed" if errors else "ok",
        "packet_path": str(packet),
        "manifest_path": str(manifest_path),
        "file_count": len(manifest_files),
        "missing_required": missing_required,
        "hash_failures": hash_failures,
        "secret_hits": scan_results["secret_hits"],
        "order_true_hits": scan_results["order_true_hits"],
        "broker_order_hits": scan_results["broker_order_hits"],
        "command_review_status": command_review.get("status"),
        "active_dangerous_hits": command_review.get("active_dangerous_commands", []),
        "errors": errors,
        "manual_approval_required": manifest.get("manual_approval_required") is True,
        "creation_executed": False,
        "remote_write_executed": False,
        "systemd_changed": False,
        "oracle_live_bot_modified": False,
        "order_execution_allowed": False,
    }


def run_command_review(packet: Path) -> dict[str, Any]:
    script = MANUAL_DIR / "review_creation_commands.py"
    result = subprocess.run(
        [sys.executable, str(script), "--packet", str(packet)],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command review did not return JSON: {result.stdout[:200]}") from exc
    return payload


def scan_packet(packet: Path) -> dict[str, list[dict[str, Any]]]:
    result = {"secret_hits": [], "order_true_hits": [], "broker_order_hits": []}
    for path in sorted(packet.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = str(path.relative_to(packet))
        add_pattern_hits(result["secret_hits"], SECRET_PATTERNS, relative, text)
        add_pattern_hits(result["order_true_hits"], ORDER_TRUE_PATTERNS, relative, text)
        add_pattern_hits(result["broker_order_hits"], BROKER_ORDER_PATTERNS, relative, text)
    return result


def add_pattern_hits(target: list[dict[str, Any]], patterns: list[re.Pattern[str]], relative: str, text: str) -> None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("echo "):
            continue
        for pattern in patterns:
            if pattern.search(stripped):
                target.append({"path": relative, "line": line_no, "pattern": pattern.pattern})


def load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name} is invalid JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{path.name} must contain an object")
        return None
    return payload


def failure(message: str) -> dict[str, Any]:
    return {"status": "failed", "errors": [message], "order_execution_allowed": False}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
