#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCAL_INBOX = ROOT / "tmp" / "oracle_pull" / "inbox"
SAFETY_BOUNDARY = (
    "AI Council does not execute trades or connect to broker APIs. "
    "This output is for review, risk analysis, and decision support only."
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preview a Mac pull workflow for Oracle US Trader outbox JSON files. "
            "Default mode does not open SSH or copy files."
        )
    )
    parser.add_argument("--host", default="<oracle-host>", help="Oracle host placeholder or value.")
    parser.add_argument("--user", default="<oracle-user>", help="Oracle SSH user placeholder or value.")
    parser.add_argument("--key", default="<path-to-private-key>", help="Private key path. Contents are never read or printed.")
    parser.add_argument("--outbox-dir", default="<oracle-outbox-dir>", help="Oracle outbox directory.")
    parser.add_argument("--local-inbox", default=str(DEFAULT_LOCAL_INBOX), help="Ignored local inbox for copied JSON files.")
    parser.add_argument("--timeout", type=float, default=30.0, help="SSH command timeout.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview only. This is the default.")
    parser.add_argument(
        "--enable-ssh-readonly-list",
        action="store_true",
        help="Run only read-only ls/find commands over SSH.",
    )
    parser.add_argument(
        "--enable-readonly-copy",
        action="store_true",
        help="Copy JSON files to the local inbox without deleting or moving remote files.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    try:
        summary = run(args)
    except Exception as exc:
        summary = base_summary(args) | {
            "status": "failed",
            "error": str(exc),
            "order_execution_allowed": False,
        }
        print_json(summary, pretty=args.pretty)
        return 1

    print_json(summary, pretty=args.pretty)
    return 0 if summary["status"] == "passed" else 1


def run(args: argparse.Namespace) -> dict[str, Any]:
    summary = base_summary(args)
    if not args.enable_ssh_readonly_list and not args.enable_readonly_copy:
        summary.update(
            {
                "status": "passed",
                "mode": "dry_run",
                "remote_listing": sample_listing(),
                "command_preview": command_preview(args),
                "note": "No SSH session was opened and no remote files were copied.",
            }
        )
        return summary

    validate_explicit_remote_args(args)
    remote_files: list[str] = []
    if args.enable_ssh_readonly_list or args.enable_readonly_copy:
        remote_files = ssh_readonly_listing(args)

    copied: list[str] = []
    if args.enable_readonly_copy:
        copied = readonly_copy(args, remote_files)

    summary.update(
        {
            "status": "passed",
            "mode": "readonly_copy" if args.enable_readonly_copy else "readonly_list",
            "ssh_readonly_list_executed": bool(args.enable_ssh_readonly_list or args.enable_readonly_copy),
            "readonly_copy_executed": bool(args.enable_readonly_copy),
            "remote_files_seen": len(remote_files),
            "copied_files": copied,
            "remote_delete_performed": False,
            "remote_move_performed": False,
        }
    )
    return summary


def base_summary(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "mac_pull_oracle_outbox",
        "oracle": {
            "host": redact_value(args.host, "<oracle-host>"),
            "user": redact_value(args.user, "<oracle-user>"),
            "ssh_key": "<path-to-private-key>",
            "outbox_dir": redact_path(args.outbox_dir, "<oracle-outbox-dir>"),
        },
        "local_inbox": str(Path(args.local_inbox).expanduser()),
        "dry_run_default": True,
        "network_changes_performed": False,
        "tunnel_started": False,
        "ssh_reverse_tunnel_started": False,
        "remote_delete_performed": False,
        "remote_move_performed": False,
        "oracle_live_bot_modified": False,
        "oracle_systemd_touched": False,
        "broker_api_used": False,
        "order_execution_allowed": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }


def command_preview(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "readonly_listing": "ssh -i <path-to-private-key> <oracle-user>@<oracle-host> 'ls -la <oracle-outbox-dir> && find <oracle-outbox-dir> -maxdepth 1 -type f -name *.json -print'",
        "readonly_copy": "scp -i <path-to-private-key> <oracle-user>@<oracle-host>:<oracle-outbox-dir>/*.json tmp/oracle_pull/inbox/",
        "remote_delete": "not allowed",
        "remote_move": "not allowed",
        "systemd": "not used",
    }


def sample_listing() -> list[dict[str, Any]]:
    return [
        {"name": "us_trader_signal_001.json", "type": "file", "order_execution_allowed": False},
        {"name": "us_trader_signal_order_like.json", "type": "file", "order_execution_allowed": False},
        {"name": "us_trader_signal_high_risk.json", "type": "file", "order_execution_allowed": False},
    ]


def validate_explicit_remote_args(args: argparse.Namespace) -> None:
    placeholders = {"<oracle-host>", "<oracle-user>", "<path-to-private-key>", "<oracle-outbox-dir>"}
    values = {args.host, args.user, args.key, args.outbox_dir}
    if values & placeholders:
        raise ValueError("explicit read-only SSH mode requires host, user, key, and outbox-dir values")
    key_path = Path(args.key).expanduser()
    if not key_path.exists():
        raise ValueError("private key path does not exist; key contents were not read")


def ssh_readonly_listing(args: argparse.Namespace) -> list[str]:
    remote_command = (
        f"ls -la {shlex.quote(args.outbox_dir)} && "
        f"find {shlex.quote(args.outbox_dir)} -maxdepth 1 -type f -name '*.json' -print"
    )
    command = ssh_base_command(args) + [remote_command]
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=args.timeout)
    files = []
    for line in result.stdout.splitlines():
        value = line.strip()
        if value.endswith(".json") and value.startswith(args.outbox_dir.rstrip("/") + "/"):
            files.append(value)
    return files


def readonly_copy(args: argparse.Namespace, remote_files: list[str]) -> list[str]:
    inbox = Path(args.local_inbox).expanduser()
    inbox.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for remote_file in remote_files:
        target = inbox / Path(remote_file).name
        source = f"{args.user}@{args.host}:{remote_file}"
        command = ["scp", "-i", str(Path(args.key).expanduser()), source, str(target)]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=args.timeout)
        copied.append(target.name)
    return copied


def ssh_base_command(args: argparse.Namespace) -> list[str]:
    return [
        "ssh",
        "-i",
        str(Path(args.key).expanduser()),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{args.user}@{args.host}",
    ]


def redact_value(value: str, placeholder: str) -> str:
    if value.startswith("<") and value.endswith(">"):
        return value
    return placeholder


def redact_path(value: str, placeholder: str) -> str:
    if value.startswith("<") and value.endswith(">"):
        return value
    return placeholder


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
