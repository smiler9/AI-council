#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FINAL_DIR = ROOT / "examples" / "oracle_final_approval"
TEMPLATES_DIR = FINAL_DIR / "templates"
DEFAULT_PRECREATION_PLAN = ROOT / "tmp" / "oracle_outbox_precreation" / "precreation_plan.json"
DEFAULT_MANUAL_COMMANDS_DIR = ROOT / "tmp" / "oracle_outbox_precreation" / "commands"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_final_approval"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)

TEMPLATE_FILES = [
    "final_approval_checklist.md",
    "read_only_precheck_commands.example.sh",
    "approved_manual_commands.example.sh",
    "post_creation_verification.example.sh",
    "approval_record.example.json",
    "rejection_record.example.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local Oracle final approval packet.")
    parser.add_argument("--precreation-plan", default=str(DEFAULT_PRECREATION_PLAN))
    parser.add_argument("--manual-commands-dir", default=str(DEFAULT_MANUAL_COMMANDS_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        result = build_packet(
            Path(args.precreation_plan),
            Path(args.manual_commands_dir),
            Path(args.output),
            force=args.force,
        )
        if args.verify:
            verify_result = run_verify(Path(args.output))
            result["verify"] = verify_result
            if verify_result.get("status") != "ok":
                result["status"] = "failed"
    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "order_execution_allowed": False}
        print_json(result, pretty=args.pretty)
        return 1

    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def build_packet(precreation_plan: Path, manual_commands_dir: Path, output_dir: Path, *, force: bool) -> dict[str, Any]:
    plan_path = precreation_plan.expanduser().resolve()
    commands_dir = manual_commands_dir.expanduser().resolve()
    output = output_dir.expanduser().resolve()
    if not plan_path.exists():
        raise FileNotFoundError(f"precreation plan not found: {plan_path}")
    if not commands_dir.exists():
        raise FileNotFoundError(f"manual commands directory not found: {commands_dir}")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    command_review = run_command_review(commands_dir)
    if command_review.get("status") != "passed":
        raise RuntimeError("manual command review failed; refusing to build final approval packet")

    reset_output_dir(output, force=force)
    output.mkdir(parents=True, exist_ok=True)

    copied_files: list[dict[str, Any]] = []
    for name in TEMPLATE_FILES:
        source = TEMPLATES_DIR / name
        if not source.exists():
            raise FileNotFoundError(f"required final approval template missing: {source}")
        destination = output / name
        shutil.copy2(source, destination)
        copied_files.append(file_entry(destination, Path(name), source))

    review_path = output / "manual_command_review.json"
    review_path.write_text(json.dumps(command_review, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    copied_files.append(file_entry(review_path, Path("manual_command_review.json"), commands_dir))

    source_summary = {
        "precreation_plan_path": safe_source_label(plan_path),
        "manual_commands_dir": safe_source_label(commands_dir),
        "plan_sha256": sha256_file(plan_path),
        "manual_command_file_count": command_review.get("files_reviewed", 0),
        "precreation_plan": {
            "mode": plan.get("mode"),
            "manual_approval_required": plan.get("manual_approval_required"),
            "remote_write_executed": plan.get("remote_write_executed"),
            "remote_delete": plan.get("remote_delete"),
            "remote_move": plan.get("remote_move"),
            "systemd_changes_planned": plan.get("systemd_changes_planned"),
            "order_execution_allowed": plan.get("order_execution_allowed"),
        },
    }

    manifest = {
        "status": "ok",
        "packet_name": "oracle_final_approval_packet",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packet_path": str(output),
        "files": copied_files,
        "file_count": len(copied_files),
        "source_summary": source_summary,
        "manual_approval_required": True,
        "approved": False,
        "remote_write_executed": False,
        "remote_delete": False,
        "remote_move": False,
        "systemd_changes_planned": False,
        "oracle_server_contacted": False,
        "oracle_live_bot_modified": False,
        "broker_api_connected": False,
        "order_execution_allowed": False,
        "simulation_only": True,
        "safety_boundary": SAFETY_BOUNDARY,
        "safety_notes": [
            "Packet generation is local only.",
            "Approval record defaults to approved=false.",
            "Read-only precheck commands and manual write candidates are separated.",
            "Write candidates remain commented until a separate manual approval.",
            "AI Council does not execute trades or connect to broker APIs.",
        ],
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "status": "ok",
        "packet_path": str(output),
        "manifest_path": str(manifest_path),
        "file_count": len(copied_files),
        "manual_command_review_status": command_review.get("status"),
        "manual_approval_required": True,
        "approved": False,
        "remote_write_executed": False,
        "order_execution_allowed": False,
    }


def reset_output_dir(output: Path, *, force: bool) -> None:
    if not output.exists():
        return
    if not output.is_dir():
        raise RuntimeError(f"output exists and is not a directory: {output}")
    if any(output.iterdir()) and not force:
        raise RuntimeError(f"output directory is not empty; pass --force for generated packet output: {output}")
    if force:
        ensure_generated_output_path(output)
        shutil.rmtree(output)


def ensure_generated_output_path(output: Path) -> None:
    allowed_roots = [
        (ROOT / "tmp" / "oracle_final_approval").resolve(),
        (FINAL_DIR / "output").resolve(),
    ]
    if not any(output == root or output.is_relative_to(root) for root in allowed_roots):
        raise RuntimeError(f"refusing to remove non-generated output directory: {output}")


def run_command_review(commands_dir: Path) -> dict[str, Any]:
    script = FINAL_DIR / "review_manual_commands.py"
    result = subprocess.run(
        [sys.executable, str(script), "--commands-dir", str(commands_dir)],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"manual command review did not return JSON: {result.stdout[:200]}") from exc
    if result.returncode != 0 and payload.get("status") == "passed":
        payload["status"] = "failed"
    return payload


def run_verify(packet_dir: Path) -> dict[str, Any]:
    script = FINAL_DIR / "verify_final_approval_packet.py"
    result = subprocess.run(
        [sys.executable, str(script), "--packet", str(packet_dir)],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"verify did not return JSON: {result.stdout[:200]}") from exc
    if result.returncode != 0 and payload.get("status") == "ok":
        payload["status"] = "failed"
    return payload


def file_entry(path: Path, relative: Path, source: Path) -> dict[str, Any]:
    return {
        "path": str(relative),
        "source": safe_source_label(source),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def safe_source_label(source: Path) -> str:
    try:
        return str(source.resolve().relative_to(ROOT))
    except ValueError:
        return source.name


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
