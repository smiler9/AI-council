#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN = ROOT / "tmp" / "oracle_preview_deploy_plan.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_preview_commands"
TEMPLATES_DIR = ROOT / "examples" / "oracle_preview_deploy" / "templates"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate manual preview-only Oracle sidecar command files.")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="Preview deploy plan JSON path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Ignored command preview output directory.")
    parser.add_argument("--force", action="store_true", help="Replace generated command output directory.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    try:
        result = generate_commands(Path(args.plan), Path(args.output), force=args.force)
    except Exception as exc:
        result = {
            "status": "failed",
            "error": str(exc),
            "oracle_server_contacted": False,
            "oracle_files_written": False,
            "order_execution_allowed": False,
        }
        print_json(result, pretty=args.pretty)
        return 1

    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def generate_commands(plan_path: Path, output_dir: Path, *, force: bool = False) -> dict[str, Any]:
    plan = json.loads(plan_path.expanduser().read_text(encoding="utf-8"))
    if plan.get("mode") != "preview":
        raise RuntimeError("refusing to generate commands for non-preview plan")
    output = output_dir.expanduser().resolve()
    reset_output_dir(output, force=force)
    output.mkdir(parents=True, exist_ok=True)

    files = {
        "00_readiness_check.sh": readiness_script(plan),
        "01_create_sidecar_dirs.preview.sh": create_dirs_script(plan),
        "02_upload_bundle.preview.sh": upload_bundle_script(plan),
        "03_verify_remote_files.preview.sh": verify_remote_script(plan),
        "04_run_sidecar_once_preview.preview.sh": run_once_script(plan),
        "05_check_logs.preview.sh": check_logs_script(plan),
        "99_rollback_preview.preview.sh": rollback_script(plan),
    }
    written = []
    for name, text in files.items():
        path = output / name
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)
        written.append(str(path))

    template_output = output / "templates"
    template_output.mkdir(exist_ok=True)
    for template in TEMPLATES_DIR.glob("*"):
        shutil.copy2(template, template_output / template.name)
        written.append(str(template_output / template.name))

    return {
        "status": "ok",
        "plan_path": str(plan_path.expanduser()),
        "output_dir": str(output),
        "command_file_count": len(files),
        "files": written,
        "mode": "preview",
        "oracle_server_contacted": False,
        "oracle_files_written": False,
        "oracle_systemd_touched": False,
        "order_execution_allowed": False,
    }


def reset_output_dir(output: Path, *, force: bool) -> None:
    if not output.exists():
        return
    if not output.is_dir():
        raise RuntimeError(f"output exists and is not a directory: {output}")
    if any(output.iterdir()) and not force:
        raise RuntimeError(f"output directory is not empty; pass --force: {output}")
    if force:
        allowed = [
            (ROOT / "tmp").resolve(),
            (ROOT / "examples" / "oracle_preview_deploy" / "output").resolve(),
            (ROOT / "examples" / "oracle_preview_deploy" / "commands").resolve(),
        ]
        if not any(output == root or output.is_relative_to(root) for root in allowed):
            raise RuntimeError(f"refusing to remove non-generated output directory: {output}")
        shutil.rmtree(output)


def header(title: str) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        f"echo \"{title}\"\n"
        "echo \"Preview-only command file. Review manually before any Oracle action.\"\n"
        "echo \"No broker API. No real order. order_execution_allowed=false\"\n\n"
    )


def readiness_script(plan: dict[str, Any]) -> str:
    return header("00 read-only readiness check") + (
        "echo \"Run local dry-run first: scripts/run_oracle_readiness_check_dryrun.sh\"\n"
        f"echo \"Target placeholder: {plan['oracle_target']['user']}@{plan['oracle_target']['host']}\"\n"
        "echo \"Optional read-only SSH check requires separate approval.\"\n"
    )


def create_dirs_script(plan: dict[str, Any]) -> str:
    return header("01 create sidecar dirs preview") + (
        f"echo \"Would create sidecar dir: {plan['sidecar_dir']}\"\n"
        f"echo \"Would create outbox dir: {plan['outbox_dir']}\"\n"
        f"echo \"Would create processed dir: {plan['processed_dir']}\"\n"
        f"echo \"Would create failed dir: {plan['failed_dir']}\"\n"
        "echo \"Manual approval required before any remote mkdir.\"\n"
    )


def upload_bundle_script(plan: dict[str, Any]) -> str:
    return header("02 upload bundle preview") + (
        f"echo \"Bundle path: {plan['bundle_path']}\"\n"
        f"echo \"Would manually place bundle files under: {plan['sidecar_dir']}\"\n"
        "echo \"No upload is performed by this generated file.\"\n"
    )


def verify_remote_script(plan: dict[str, Any]) -> str:
    return header("03 verify remote files preview") + (
        f"echo \"Would verify env file exists: {plan['env_file_path']}\"\n"
        f"echo \"Would verify sidecar bridge exists under: {plan['sidecar_dir']}\"\n"
        "echo \"Would run sidecar dry-run with --mode preview only after manual approval.\"\n"
    )


def run_once_script(plan: dict[str, Any]) -> str:
    return header("04 run sidecar once preview") + (
        "echo \"Run-once preview command:\"\n"
        f"echo {json.dumps(plan['run_once_command_preview'])}\n"
        "echo \"This calls AI Council normalize-preview through sidecar preview mode.\"\n"
    )


def check_logs_script(plan: dict[str, Any]) -> str:
    return header("05 check logs preview") + (
        "echo \"Read-only log checks only.\"\n"
        f"echo \"Would inspect sidecar state under: {plan['sidecar_dir']}/state\"\n"
        "echo \"Would inspect sidecar log file if configured.\"\n"
        "echo \"Do not operate Oracle live bot services.\"\n"
    )


def rollback_script(plan: dict[str, Any]) -> str:
    return header("99 rollback preview") + (
        "echo \"Rollback preview only. Manual approval required before removing sidecar preview files.\"\n"
        f"echo \"Target sidecar dir: {plan['sidecar_dir']}\"\n"
        "echo \"Do not modify penny_stock_bot.py. Do not operate production services.\"\n"
    )


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
