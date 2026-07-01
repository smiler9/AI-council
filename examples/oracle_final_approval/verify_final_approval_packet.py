#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_FILES = {
    "final_approval_checklist.md",
    "read_only_precheck_commands.example.sh",
    "approved_manual_commands.example.sh",
    "post_creation_verification.example.sh",
    "approval_record.example.json",
    "rejection_record.example.json",
    "manual_command_review.json",
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
APPROVED_TRUE_PATTERNS = [
    re.compile(r'"approved"\s*:\s*true', re.IGNORECASE),
    re.compile(r"\bapproved\s*=\s*true\b", re.IGNORECASE),
]
ACTIVE_DANGEROUS_PATTERNS = [
    re.compile(r"\bmkdir\s+"),
    re.compile(r"\btouch\s+"),
    re.compile(r"\bcp\s+"),
    re.compile(r"\bmv\s+"),
    re.compile(r"\brm\s+"),
    re.compile(r"\bchmod\s+"),
    re.compile(r"\bchown\s+"),
    re.compile(r"\bsystemctl\s+(?:start|stop|restart|reload|enable|disable)\b"),
    re.compile(r"\bdocker\s+(?:start|stop|restart)\b"),
    re.compile(r"\bservice\s+\S+\s+(?:start|stop|restart)\b"),
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
    parser = argparse.ArgumentParser(description="Verify a local Oracle final approval packet.")
    parser.add_argument("--packet", required=True)
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
    if scan_results["approved_true_hits"]:
        errors.append("approved true marker found")
    if scan_results["active_dangerous_hits"]:
        errors.append("active dangerous command found")

    approval_payload = load_json(packet / "approval_record.example.json", errors)
    command_review = load_json(packet / "manual_command_review.json", errors)

    if manifest.get("manual_approval_required") is not True:
        errors.append("manifest manual_approval_required must be true")
    if manifest.get("approved") is not False:
        errors.append("manifest approved must be false")
    if manifest.get("remote_write_executed") is not False:
        errors.append("manifest remote_write_executed must be false")
    if manifest.get("order_execution_allowed") is not False:
        errors.append("manifest order_execution_allowed must be false")
    if manifest.get("systemd_changes_planned") is not False:
        errors.append("manifest systemd_changes_planned must be false")
    if approval_payload:
        if approval_payload.get("approved") is not False:
            errors.append("approval_record approved must default to false")
        if approval_payload.get("order_execution_allowed") is not False:
            errors.append("approval_record order_execution_allowed must be false")
    if command_review:
        if command_review.get("status") != "passed":
            errors.append("manual_command_review status must be passed")
        if command_review.get("active_dangerous_commands_found") is not False:
            errors.append("manual_command_review active_dangerous_commands_found must be false")

    return {
        "status": "failed" if errors else "ok",
        "packet_path": str(packet),
        "manifest_path": str(manifest_path),
        "file_count": len(manifest_files),
        "missing_required": missing_required,
        "hash_failures": hash_failures,
        "secret_hits": scan_results["secret_hits"],
        "order_true_hits": scan_results["order_true_hits"],
        "approved_true_hits": scan_results["approved_true_hits"],
        "active_dangerous_hits": scan_results["active_dangerous_hits"],
        "errors": errors,
        "manual_approval_required": manifest.get("manual_approval_required") is True,
        "approved": False,
        "remote_write_executed": False,
        "systemd_changes_planned": False,
        "oracle_systemd_touched": False,
        "order_execution_allowed": False,
    }


def scan_packet(packet: Path) -> dict[str, list[dict[str, Any]]]:
    result = {
        "secret_hits": [],
        "order_true_hits": [],
        "approved_true_hits": [],
        "active_dangerous_hits": [],
    }
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
        add_pattern_hits(result["approved_true_hits"], APPROVED_TRUE_PATTERNS, relative, text)
        if path.suffix in {".sh", ".service", ".txt"}:
            add_active_dangerous_hits(result["active_dangerous_hits"], relative, text)
    return result


def add_pattern_hits(target: list[dict[str, Any]], patterns: list[re.Pattern[str]], relative: str, text: str) -> None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            if pattern.search(line):
                target.append({"path": relative, "line": line_no, "pattern": pattern.pattern})


def add_active_dangerous_hits(target: list[dict[str, Any]], relative: str, text: str) -> None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("echo ") or stripped.startswith("printf "):
            continue
        for pattern in ACTIVE_DANGEROUS_PATTERNS:
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
