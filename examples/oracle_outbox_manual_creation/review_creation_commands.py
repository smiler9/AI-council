#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKET = ROOT / "tmp" / "oracle_outbox_manual_creation"

WRITE_COMMAND_PATTERNS = [
    re.compile(r"^\s*mkdir\b"),
    re.compile(r"^\s*touch\b"),
    re.compile(r"^\s*cp\b"),
    re.compile(r"^\s*mv\b"),
    re.compile(r"^\s*rm\b"),
    re.compile(r"^\s*rmdir\b"),
    re.compile(r"^\s*chmod\b"),
    re.compile(r"^\s*chown\b"),
]
SYSTEM_COMMAND_PATTERNS = [
    re.compile(r"^\s*systemctl\s+(?:start|stop|restart|reload)\b"),
    re.compile(r"^\s*docker\s+(?:start|stop|restart)\b"),
    re.compile(r"^\s*service\s+\S+\s+(?:start|stop|restart)\b"),
]
ORDER_COMMAND_PATTERNS = [
    re.compile(r"\bpython(?:3)?\s+penny_stock_bot\.py\b"),
    re.compile(r"\bplace_order\b"),
    re.compile(r"\bsubmit_order\b"),
    re.compile(r"\bcreate_order\b"),
    re.compile(r"\bcancel_order\b"),
    re.compile(r"\bclose_position\b"),
    re.compile(r"\bbroker\b.*\border\b", re.IGNORECASE),
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
    re.compile(r"ORDER_EXECUTION_ALLOWED\s*=\s*true", re.IGNORECASE),
]
READ_ONLY_PREFIXES = (
    "echo ",
    "printf ",
    "test ",
    "ls ",
    "stat ",
    "df ",
    "free ",
    "python --version",
    "python3 --version",
    "which python3",
    "set -euo pipefail",
    "pwd",
    "whoami",
    "date",
    "uname ",
)
SECRET_TARGET_PATTERNS = [
    re.compile(r"\.secrets", re.IGNORECASE),
    re.compile(r"\.env\b", re.IGNORECASE),
    re.compile(r"kis_config", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Review Oracle outbox manual creation packet commands.")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = review_packet(Path(args.packet))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "passed" else 1


def review_packet(packet_dir: Path) -> dict[str, Any]:
    packet = packet_dir.expanduser().resolve()
    if not packet.exists():
        return failure(f"packet directory not found: {packet}")

    files = sorted(path for path in packet.glob("*.sh") if path.is_file())
    errors: list[str] = []
    warnings: list[str] = []
    active_dangerous: list[dict[str, Any]] = []
    commented_manual_write_commands: list[dict[str, Any]] = []
    read_only_commands: list[dict[str, Any]] = []
    secret_hits: list[dict[str, Any]] = []
    order_true_hits: list[dict[str, Any]] = []
    commented_systemd_hits: list[dict[str, Any]] = []

    for path in files:
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(packet))
        add_pattern_hits(secret_hits, SECRET_PATTERNS, relative, text)
        add_pattern_hits(order_true_hits, ORDER_TRUE_PATTERNS, relative, text)
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            record = {"path": relative, "line": line_no, "command": stripped}
            if stripped.startswith("#"):
                uncommented = stripped.lstrip("#").strip()
                if is_system_command(uncommented):
                    commented_systemd_hits.append(record)
                    warnings.append(f"commented systemd command present in {relative}:{line_no}")
                if is_write_command(uncommented):
                    commented_manual_write_commands.append(record)
                if any(pattern.search(uncommented) for pattern in ORDER_COMMAND_PATTERNS):
                    active_dangerous.append(record)
                continue
            if is_dangerous_active_line(stripped):
                active_dangerous.append(record)
                continue
            if is_read_only_line(stripped):
                read_only_commands.append(record)
                continue
            errors.append(f"unclassified active command in {relative}:{line_no}: {stripped}")

    if active_dangerous:
        errors.append("active dangerous command found")
    if secret_hits:
        errors.append("secret/private key/token/oracle host marker found")
    if order_true_hits:
        errors.append("order_execution_allowed true marker found")

    return {
        "status": "failed" if errors else "passed",
        "packet_path": str(packet),
        "files_reviewed": len(files),
        "active_dangerous_commands_found": bool(active_dangerous),
        "active_dangerous_commands": active_dangerous,
        "commented_manual_write_commands": commented_manual_write_commands,
        "commented_systemd_hits": commented_systemd_hits,
        "read_only_commands": read_only_commands,
        "secret_hits": secret_hits,
        "order_true_hits": order_true_hits,
        "warnings": warnings,
        "errors": errors,
        "creation_executed": False,
        "remote_write_executed": False,
        "remote_delete": False,
        "remote_move": False,
        "remote_permission_changed": False,
        "systemd_changed": False,
        "oracle_live_bot_modified": False,
        "order_execution_allowed": False,
    }


def is_dangerous_active_line(line: str) -> bool:
    if line.startswith("echo ") or line.startswith("printf "):
        return False
    if line.startswith("cat ") and any(pattern.search(line) for pattern in SECRET_TARGET_PATTERNS):
        return True
    return is_write_command(line) or is_system_command(line) or any(pattern.search(line) for pattern in ORDER_COMMAND_PATTERNS)


def is_write_command(line: str) -> bool:
    return any(pattern.search(line) for pattern in WRITE_COMMAND_PATTERNS)


def is_system_command(line: str) -> bool:
    return any(pattern.search(line) for pattern in SYSTEM_COMMAND_PATTERNS)


def is_read_only_line(line: str) -> bool:
    if re.match(r"^[A-Z_]+=", line):
        return True
    if line.startswith("cat "):
        return not any(pattern.search(line) for pattern in SECRET_TARGET_PATTERNS)
    return line.startswith(READ_ONLY_PREFIXES)


def add_pattern_hits(target: list[dict[str, Any]], patterns: list[re.Pattern[str]], relative: str, text: str) -> None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            if pattern.search(line):
                target.append({"path": relative, "line": line_no, "pattern": pattern.pattern})


def failure(message: str) -> dict[str, Any]:
    return {"status": "failed", "errors": [message], "order_execution_allowed": False}


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
