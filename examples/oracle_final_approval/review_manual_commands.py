#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMMANDS_DIR = ROOT / "tmp" / "oracle_outbox_precreation" / "commands"

WRITE_COMMAND_PATTERNS = [
    re.compile(r"^\s*mkdir\b"),
    re.compile(r"^\s*touch\b"),
    re.compile(r"^\s*cp\b"),
    re.compile(r"^\s*mv\b"),
    re.compile(r"^\s*rm\b"),
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
    parser = argparse.ArgumentParser(description="Review manual Oracle command examples before final approval.")
    parser.add_argument("--commands-dir", default=str(DEFAULT_COMMANDS_DIR))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    result = review_manual_commands(Path(args.commands_dir))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "passed" else 1


def review_manual_commands(commands_dir: Path) -> dict[str, Any]:
    directory = commands_dir.expanduser().resolve()
    if not directory.exists():
        return {
            "status": "failed",
            "errors": [f"commands directory not found: {directory}"],
            "active_dangerous_commands_found": True,
            "order_execution_allowed": False,
        }

    files = sorted(path for path in directory.glob("*.sh") if path.is_file())
    errors: list[str] = []
    active_dangerous: list[dict[str, Any]] = []
    commented_manual_write_commands: list[dict[str, Any]] = []
    read_only_commands: list[dict[str, Any]] = []

    for path in files:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            record = {"path": str(path.relative_to(directory)), "line": line_no, "command": stripped}
            if stripped.startswith("#"):
                uncommented = stripped.lstrip("#").strip()
                if is_write_or_system_command(uncommented):
                    commented_manual_write_commands.append(record)
                continue
            if is_dangerous_active_line(stripped):
                active_dangerous.append(record)
                continue
            if is_read_only_line(stripped):
                read_only_commands.append(record)
                continue
            errors.append(f"unclassified active command in {record['path']}:{line_no}: {stripped}")

    if active_dangerous:
        errors.append("active dangerous command found")

    return {
        "status": "failed" if errors else "passed",
        "commands_dir": str(directory),
        "files_reviewed": len(files),
        "active_dangerous_commands_found": bool(active_dangerous),
        "active_dangerous_commands": active_dangerous,
        "commented_manual_write_commands": commented_manual_write_commands,
        "read_only_commands": read_only_commands,
        "errors": errors,
        "remote_write_executed": False,
        "remote_delete": False,
        "remote_move": False,
        "systemd_changes_executed": False,
        "oracle_live_bot_modified": False,
        "order_execution_allowed": False,
    }


def is_dangerous_active_line(line: str) -> bool:
    if line.startswith("cat ") and any(pattern.search(line) for pattern in SECRET_TARGET_PATTERNS):
        return True
    return is_write_or_system_command(line) or any(pattern.search(line) for pattern in ORDER_COMMAND_PATTERNS)


def is_write_or_system_command(line: str) -> bool:
    return any(pattern.search(line) for pattern in WRITE_COMMAND_PATTERNS + SYSTEM_COMMAND_PATTERNS)


def is_read_only_line(line: str) -> bool:
    if line.startswith("cat "):
        return not any(pattern.search(line) for pattern in SECRET_TARGET_PATTERNS)
    return line.startswith(READ_ONLY_PREFIXES)


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
