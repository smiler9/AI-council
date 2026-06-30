#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any


DEFAULT_SERVICES = ["sniper-bot.service", "usstock-bot.service", "usstock-web.service"]
PLACEHOLDER_HOST = "<oracle-host>"
PLACEHOLDER_USER = "<oracle-user>"
PLACEHOLDER_KEY = "<path-to-private-key>"
PLACEHOLDER_TRADING_DIR = "<oracle-trading-dir>"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Oracle readiness check preview.")
    parser.add_argument("--host", default=PLACEHOLDER_HOST, help="Oracle host. Placeholder is used for dry-run.")
    parser.add_argument("--user", default=PLACEHOLDER_USER, help="Oracle user. Placeholder is used for dry-run.")
    parser.add_argument("--key", default=PLACEHOLDER_KEY, help="Private key path. The value is never printed.")
    parser.add_argument("--trading-dir", default=PLACEHOLDER_TRADING_DIR, help="Oracle trading directory.")
    parser.add_argument(
        "--service",
        action="append",
        dest="services",
        help="Service to check with systemctl status --no-pager. Can be repeated.",
    )
    parser.add_argument(
        "--enable-ssh-readonly-check",
        action="store_true",
        help="Actually run read-only SSH checks. Default is command preview only.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview read-only commands without SSH. This is the default.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    services = args.services or DEFAULT_SERVICES
    result = readiness_check(
        host=args.host,
        user=args.user,
        key=args.key,
        trading_dir=args.trading_dir,
        services=services,
        enable_ssh=args.enable_ssh_readonly_check,
    )
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def readiness_check(
    *,
    host: str,
    user: str,
    key: str,
    trading_dir: str,
    services: list[str],
    enable_ssh: bool,
) -> dict[str, Any]:
    commands = build_read_only_commands(trading_dir, services)
    dangerous = find_dangerous_commands(commands)
    if dangerous:
        return {
            "status": "failed",
            "errors": ["readiness command set contains forbidden command"],
            "dangerous_commands": dangerous,
            "order_execution_allowed": False,
        }

    preview = {
        "ssh_target": f"{user}@{host}",
        "key_path": "REDACTED" if key != PLACEHOLDER_KEY else PLACEHOLDER_KEY,
        "commands": commands,
    }

    if not enable_ssh:
        return {
            "status": "ok",
            "mode": "dry_run",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "command_preview": preview,
            "ssh_executed": False,
            "oracle_server_contacted": False,
            "oracle_files_written": False,
            "oracle_systemd_touched": False,
            "order_execution_allowed": False,
            "safety_boundary": "AI Council does not execute trades or connect to broker APIs.",
        }

    validation_error = validate_real_ssh_args(host, user, key, trading_dir)
    if validation_error:
        return {
            "status": "failed",
            "mode": "ssh_readonly",
            "error": validation_error,
            "ssh_executed": False,
            "order_execution_allowed": False,
        }

    results = []
    for command in commands:
        results.append(run_ssh_command(host, user, key, command))

    status = "ok" if all(item["returncode"] == 0 for item in results) else "failed"
    return {
        "status": status,
        "mode": "ssh_readonly",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ssh_target": f"{user}@{host}",
        "key_path": "REDACTED",
        "results": results,
        "ssh_executed": True,
        "oracle_server_contacted": True,
        "oracle_files_written": False,
        "oracle_systemd_touched": False,
        "order_execution_allowed": False,
    }


def build_read_only_commands(trading_dir: str, services: list[str]) -> list[str]:
    safe_dir = shlex.quote(trading_dir)
    commands = [
        "hostname",
        "whoami",
        "pwd",
        "uname -a",
        "date",
        f"ls -la {safe_dir}",
        f"test -f {safe_dir}/penny_stock_bot.py",
        f"test -d {safe_dir}/.secrets",
        "ps aux | grep -i trader | grep -v grep",
        "screen -ls",
        "tmux ls",
        "crontab -l",
    ]
    for service in services:
        commands.append(f"systemctl status --no-pager {shlex.quote(service)}")
    return commands


def find_dangerous_commands(commands: list[str]) -> list[str]:
    forbidden = ("systemctl start", "systemctl stop", "systemctl restart", "systemctl enable", "systemctl disable")
    forbidden += (" service ", "scp ", "rsync ", " rm ", " mv ", " cp ", " python penny_stock_bot.py")
    return [command for command in commands if any(term in f" {command} " for term in forbidden)]


def validate_real_ssh_args(host: str, user: str, key: str, trading_dir: str) -> str | None:
    if host == PLACEHOLDER_HOST or user == PLACEHOLDER_USER or key == PLACEHOLDER_KEY:
        return "host, user, and key must be explicit for --enable-ssh-readonly-check"
    if trading_dir == PLACEHOLDER_TRADING_DIR:
        return "trading-dir must be explicit for --enable-ssh-readonly-check"
    return None


def run_ssh_command(host: str, user: str, key: str, command: str) -> dict[str, Any]:
    ssh_command = [
        "ssh",
        "-i",
        key,
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        f"{user}@{host}",
        command,
    ]
    completed = subprocess.run(ssh_command, capture_output=True, text=True, timeout=20, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout_line_count": len(completed.stdout.splitlines()),
        "stderr_line_count": len(completed.stderr.splitlines()),
    }


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
