#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRECHECK_DIR = ROOT / "examples" / "oracle_readonly_precheck"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_readonly_precheck" / "precheck_plan.json"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a placeholder Oracle read-only precheck plan.")
    parser.add_argument("--oracle-trading-dir", default="<oracle-trading-dir>")
    parser.add_argument("--service-name", action="append", dest="services", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        plan = build_plan(args.oracle_trading_dir, args.services or ["<service-name>"])
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        result = {
            "status": "ok",
            "plan_path": str(output),
            "command_count": len(plan["commands"]),
            "manual_execution_required": True,
            "remote_write_allowed": False,
            "remote_write_executed": False,
            "systemd_changes_allowed": False,
            "order_execution_allowed": False,
        }
    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "order_execution_allowed": False}
        print_json(result, pretty=args.pretty)
        return 1

    print_json(result, pretty=args.pretty)
    return 0


def build_plan(trading_dir: str, services: list[str]) -> dict[str, Any]:
    trading_dir = trading_dir.rstrip("/")
    commands = [
        command("identity", "hostname", "Confirm server hostname without changing state."),
        command("identity", "whoami", "Confirm current remote user."),
        command("identity", "pwd", "Confirm shell working directory."),
        command("system_info", "uname -a", "Record kernel and architecture."),
        command("system_info", "date", "Record server date/time."),
        command("disk", "df -h", "Review disk capacity."),
        command("disk", "free -h", "Review memory status."),
        command("python_env", "python3 --version", "Confirm Python 3 availability."),
        command("python_env", "which python3", "Confirm Python 3 path."),
        command("trading_dir_exists", f"ls -la {trading_dir}", "List trading directory metadata only."),
        command("trading_dir_exists", f"test -f {trading_dir}/penny_stock_bot.py", "Check bot file existence."),
        command("trading_dir_exists", f"test -f {trading_dir}/server.py", "Check web server file existence."),
        command("trading_dir_exists", f"test -d {trading_dir}/.secrets", "Check secrets directory existence without reading it."),
        command("process_listing", "ps aux | grep -i trader", "Observe trader-related processes."),
        command("process_listing", "ps aux | grep -i penny", "Observe penny-related processes."),
        command("process_listing", "ps aux | grep -i python", "Observe Python processes."),
        command("process_listing", "screen -ls", "Observe screen sessions."),
        command("process_listing", "tmux ls", "Observe tmux sessions."),
        command("crontab_readonly", "crontab -l", "Observe current user crontab."),
    ]
    for service in services:
        commands.append(
            command(
                "service_status_readonly",
                f"systemctl status --no-pager {service}",
                "Observe service status without start/stop/restart.",
            )
        )

    return {
        "status": "ok",
        "mode": "readonly_precheck",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manual_execution_required": True,
        "remote_write_allowed": False,
        "remote_write_executed": False,
        "systemd_changes_allowed": False,
        "systemd_changed": False,
        "oracle_server_contacted": False,
        "oracle_live_bot_modified": False,
        "order_execution_allowed": False,
        "simulation_only": True,
        "commands": commands,
        "expected_observations": [
            "hostname_checked",
            "trading_dir_exists",
            "penny_stock_bot_exists",
            "server_py_exists",
            "secrets_dir_exists",
            "python3_available",
            "disk_space_ok",
            "services_observed",
        ],
        "forbidden_commands": [
            "file_write",
            "file_delete",
            "permission_change",
            "systemd_change",
            "trading_script_execution",
            "broker_order_execution",
        ],
        "result_template_path": "examples/oracle_readonly_precheck/templates/readonly_precheck_result_template.json",
        "safety_boundary": SAFETY_BOUNDARY,
    }


def command(category: str, shell: str, purpose: str) -> dict[str, str]:
    return {"category": category, "command": shell, "purpose": purpose}


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
