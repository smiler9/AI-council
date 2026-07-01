#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = ROOT / "tmp" / "oracle_outbox_precreation" / "precreation_plan.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_outbox_precreation" / "commands"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate manual-only Oracle outbox pre-creation command examples.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        summary = generate_commands(Path(args.plan), Path(args.output))
    except Exception as exc:
        summary = {"status": "failed", "error": str(exc), "order_execution_allowed": False}
        print_json(summary, pretty=args.pretty)
        return 1
    print_json(summary, pretty=args.pretty)
    return 0


def generate_commands(plan_path: Path, output_dir: Path) -> dict[str, Any]:
    plan = json.loads(plan_path.expanduser().read_text(encoding="utf-8"))
    paths = plan["paths"]
    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    files = {
        "00_check_existing_paths.manual.sh": render_check(paths),
        "01_create_outbox_dirs.manual.sh": render_create(paths),
        "02_verify_outbox_dirs.manual.sh": render_verify(paths),
        "03_permissions_review.manual.sh": render_permissions(paths),
        "99_rollback_outbox_dirs.manual.sh": render_rollback(paths),
    }
    written = []
    for name, content in files.items():
        path = output / name
        path.write_text(content, encoding="utf-8")
        written.append(str(path))

    return {
        "status": "ok",
        "plan_path": str(plan_path.expanduser()),
        "output_dir": str(output),
        "command_file_count": len(written),
        "command_files": written,
        "manual_approval_required": True,
        "remote_write_executed": False,
        "remote_delete": False,
        "remote_move": False,
        "systemd_changes_planned": False,
        "order_execution_allowed": False,
    }


def header(title: str) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        f"echo \"{title}\"\n"
        "echo \"Manual approval required before any Oracle change.\"\n"
        "echo \"No systemd operations. No live bot changes. No real orders. order_execution_allowed=false.\"\n\n"
    )


def render_check(paths: dict[str, str]) -> str:
    return header("Read-only existing path check") + "\n".join(
        [
            f"echo \"Check trading directory: {paths['trading_dir']}\"",
            f"echo \"Check outbox directory candidate: {paths['outbox_dir']}\"",
            f"# test -d {paths['trading_dir']}",
            f"# test -e {paths['outbox_dir']}",
            f"# test -e {paths['processed_dir']}",
            f"# test -e {paths['failed_dir']}",
            f"# test -e {paths['state_dir']}",
            "echo \"All read-only commands are comments for manual review.\"",
            "",
        ]
    )


def render_create(paths: dict[str, str]) -> str:
    return header("Manual outbox directory creation example") + "\n".join(
        [
            "echo \"The following creation commands are intentionally commented out.\"",
            "# 수동 승인 후에만 사람이 복사해서 실행할 수 있는 예시입니다.",
            f"# mkdir -p {paths['outbox_dir']}",
            f"# mkdir -p {paths['processed_dir']}",
            f"# mkdir -p {paths['failed_dir']}",
            f"# mkdir -p {paths['state_dir']}",
            "echo \"This script itself does not create directories.\"",
            "",
        ]
    )


def render_verify(paths: dict[str, str]) -> str:
    return header("Manual outbox directory verification example") + "\n".join(
        [
            "echo \"The following read-only verification commands are comments.\"",
            f"# test -d {paths['outbox_dir']}",
            f"# test -d {paths['processed_dir']}",
            f"# test -d {paths['failed_dir']}",
            f"# test -d {paths['state_dir']}",
            f"# ls -ld {paths['outbox_dir']} {paths['processed_dir']} {paths['failed_dir']} {paths['state_dir']}",
            "echo \"No remote files are deleted, moved, or modified.\"",
            "",
        ]
    )


def render_permissions(paths: dict[str, str]) -> str:
    return header("Manual permissions review example") + "\n".join(
        [
            "echo \"Review owner/group manually. Permission changes are comments only.\"",
            f"# ls -ld {paths['outbox_dir']} {paths['processed_dir']} {paths['failed_dir']} {paths['state_dir']}",
            f"# chmod 750 {paths['outbox_dir']}",
            "echo \"No active chmod/chown command is executed by this file.\"",
            "",
        ]
    )


def render_rollback(paths: dict[str, str]) -> str:
    return header("Manual rollback planning example") + "\n".join(
        [
            "echo \"Rollback defaults to preserving outbox files and stopping Mac pull.\"",
            "echo \"Remote deletion is prohibited by default.\"",
            f"# rm -r {paths['outbox_dir']}  # prohibited unless separately approved after audit",
            f"# mv {paths['outbox_dir']} <approved-archive-dir>  # prohibited unless separately approved",
            "echo \"No active rm/mv command is executed by this file.\"",
            "",
        ]
    )


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
