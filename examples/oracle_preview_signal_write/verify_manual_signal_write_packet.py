#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_FILES = [
    "us_trader_preview_signal.json",
    "manual_signal_write_commands.example.sh",
    "post_signal_write_verify_commands.example.sh",
    "signal_write_result_template.json",
    "manifest.json",
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
ACTIVE_DANGEROUS = re.compile(
    r"^\s*(scp|rsync|mkdir|touch|chmod|chown|rm\s+|rmdir\s+|mv\s+|systemctl\b|service\b|docker\b)\b"
)
COMMENTED_MANUAL = re.compile(r"^\s*#\s*(scp|rsync|mkdir|chmod|chown|rm\s+|rmdir\s+|mv\s+|systemctl\b)")
BROKER_ORDER_RISK = re.compile(
    r"\b(submit_order|create_order|cancel_order|close_position|market_order|limit_order)\s*\(",
    re.IGNORECASE,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a local Oracle preview signal manual write packet.")
    parser.add_argument("--packet", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = verify_packet(Path(args.packet))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def verify_packet(packet_dir: Path) -> dict[str, Any]:
    packet = packet_dir.expanduser().resolve()
    if not packet.exists():
        return failure(f"packet not found: {packet}")
    errors: list[str] = []
    warnings: list[str] = []
    required_missing = [name for name in REQUIRED_FILES if not (packet / name).exists()]
    if required_missing:
        errors.append(f"required files missing: {required_missing}")

    manifest_path = packet / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("files", []):
            rel = entry.get("path")
            expected = entry.get("sha256")
            if not rel or not expected:
                errors.append("manifest file entry missing path or sha256")
                continue
            file_path = packet / rel
            if not file_path.exists():
                errors.append(f"manifest file missing: {rel}")
            elif sha256_file(file_path) != expected:
                errors.append(f"sha256 mismatch: {rel}")
        for key in ["remote_write_executed", "systemd_changed", "oracle_live_bot_modified", "penny_stock_bot_modified", "order_execution_allowed"]:
            if manifest.get(key) is not False:
                errors.append(f"manifest {key} must be false")
        if manifest.get("manual_approval_required") is not True:
            errors.append("manifest manual_approval_required must be true")

    text_parts: list[str] = []
    active_dangerous: list[str] = []
    commented_manual: list[str] = []
    for path in packet.glob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            text_parts.append(text)
            if path.suffix == ".sh":
                scan = scan_shell(path)
                active_dangerous.extend(scan["active_dangerous"])
                commented_manual.extend(scan["commented_manual"])

    combined = "\n".join(text_parts)
    secret_hits = pattern_hits(SECRET_PATTERNS, combined)
    order_true_hits = pattern_hits(ORDER_TRUE_PATTERNS, combined)
    broker_order_hits = pattern_hits([BROKER_ORDER_RISK], combined)
    if active_dangerous:
        errors.append(f"active dangerous commands found: {active_dangerous}")
    if secret_hits:
        errors.append("secret/private key/token/oracle host marker found")
    if order_true_hits:
        errors.append("order_execution_allowed true marker found")
    if broker_order_hits:
        errors.append("broker/order execution function marker found")
    if not commented_manual:
        warnings.append("no commented manual upload command candidates found")

    return {
        "status": "ok" if not errors else "failed",
        "packet_path": str(packet),
        "required_missing": required_missing,
        "active_dangerous_commands_found": bool(active_dangerous),
        "active_dangerous_commands": active_dangerous,
        "commented_manual_commands": commented_manual,
        "secret_hits": secret_hits,
        "order_true_hits": order_true_hits,
        "broker_order_hits": broker_order_hits,
        "errors": errors,
        "warnings": warnings,
        "remote_write_executed": False,
        "systemd_changed": False,
        "order_execution_allowed": False,
    }


def scan_shell(path: Path) -> dict[str, list[str]]:
    active: list[str] = []
    commented: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if COMMENTED_MANUAL.search(stripped):
                commented.append(f"{path.name}:{number}:{stripped}")
            continue
        if ACTIVE_DANGEROUS.search(stripped):
            active.append(f"{path.name}:{number}:{stripped}")
    return {"active_dangerous": active, "commented_manual": commented}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
