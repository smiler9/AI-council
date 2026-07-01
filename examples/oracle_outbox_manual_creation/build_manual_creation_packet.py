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
MANUAL_DIR = ROOT / "examples" / "oracle_outbox_manual_creation"
TEMPLATES_DIR = MANUAL_DIR / "templates"
DEFAULT_PRECREATION_PLAN = ROOT / "tmp" / "oracle_outbox_precreation" / "precreation_plan.json"
DEFAULT_GO_NO_GO_DECISION = ROOT / "tmp" / "oracle_precheck_intake" / "go_no_go_decision.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_outbox_manual_creation"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)

PACKET_FILES = [
    "manual_creation_commands.example.sh",
    "post_creation_verify_commands.example.sh",
    "creation_result_record.example.json",
    "rollback_after_creation.example.sh",
    "manual_creation_checklist.md",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local Oracle outbox manual creation command packet.")
    parser.add_argument("--precreation-plan", default=str(DEFAULT_PRECREATION_PLAN))
    parser.add_argument("--go-no-go-decision", default=str(DEFAULT_GO_NO_GO_DECISION))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        result = build_packet(
            Path(args.precreation_plan),
            Path(args.go_no_go_decision),
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


def build_packet(precreation_plan: Path, go_no_go_decision: Path, output_dir: Path, *, force: bool) -> dict[str, Any]:
    plan_path = precreation_plan.expanduser().resolve()
    decision_path = go_no_go_decision.expanduser().resolve()
    output = output_dir.expanduser().resolve()
    if not plan_path.exists():
        raise FileNotFoundError(f"precreation plan not found: {plan_path}")
    if not decision_path.exists():
        raise FileNotFoundError(f"go/no-go decision not found: {decision_path}")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    validate_inputs(plan, decision)
    reset_output_dir(output, force=force)
    output.mkdir(parents=True, exist_ok=True)

    paths = plan["paths"]
    files = {
        "manual_creation_commands.example.sh": render_manual_creation_commands(paths),
        "post_creation_verify_commands.example.sh": render_post_creation_verify_commands(paths),
        "creation_result_record.example.json": json.dumps(build_creation_result_record(paths), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        "rollback_after_creation.example.sh": render_rollback_after_creation(paths),
        "manual_creation_checklist.md": render_manual_creation_checklist(paths),
    }

    manifest_files: list[dict[str, Any]] = []
    for name, content in files.items():
        destination = output / name
        destination.write_text(content, encoding="utf-8")
        manifest_files.append(file_entry(destination, Path(name), "generated_from_phase_24p_template"))

    command_review = run_command_review(output)
    review_path = output / "creation_command_review.json"
    review_path.write_text(json.dumps(command_review, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest_files.append(file_entry(review_path, Path("creation_command_review.json"), "review_creation_commands.py"))
    if command_review.get("status") != "passed":
        raise RuntimeError("creation command review failed; refusing to finish packet")

    manifest = {
        "status": "ok",
        "packet_name": "oracle_outbox_manual_creation_packet",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packet_path": str(output),
        "files": manifest_files,
        "file_count": len(manifest_files),
        "source_summary": {
            "precreation_plan_path": safe_source_label(plan_path),
            "go_no_go_decision_path": safe_source_label(decision_path),
            "precreation_plan_sha256": sha256_file(plan_path),
            "go_no_go_decision_sha256": sha256_file(decision_path),
            "decision": decision.get("decision"),
            "next_phase_allowed": decision.get("next_phase_allowed"),
            "plan_mode": plan.get("mode"),
        },
        "manual_approval_required": True,
        "go_is_not_deployment_approval": True,
        "creation_executed": False,
        "remote_write_executed": False,
        "remote_delete": False,
        "remote_move": False,
        "remote_permission_change_executed": False,
        "systemd_changed": False,
        "oracle_live_bot_modified": False,
        "broker_api_connected": False,
        "order_execution_allowed": False,
        "simulation_only": True,
        "safety_boundary": SAFETY_BOUNDARY,
        "safety_notes": [
            "Packet generation is local only.",
            "All directory creation commands are commented manual examples.",
            "GO only allows this packet review stage, not deployment.",
            "No Oracle service, live bot, broker API, or order path is touched.",
        ],
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "status": "ok",
        "packet_path": str(output),
        "manifest_path": str(manifest_path),
        "command_review_status": command_review.get("status"),
        "manual_approval_required": True,
        "creation_executed": False,
        "remote_write_executed": False,
        "systemd_changed": False,
        "order_execution_allowed": False,
    }


def validate_inputs(plan: dict[str, Any], decision: dict[str, Any]) -> None:
    errors: list[str] = []
    if decision.get("decision") != "GO":
        errors.append("go/no-go decision must be GO")
    if decision.get("next_phase_allowed") is not True:
        errors.append("next_phase_allowed must be true")
    if decision.get("order_execution_allowed") is not False:
        errors.append("decision order_execution_allowed must be false")
    if decision.get("remote_write_executed") is not False:
        errors.append("decision remote_write_executed must be false")
    if decision.get("systemd_changed") is not False:
        errors.append("decision systemd_changed must be false")
    if decision.get("live_bot_modified") is not False:
        errors.append("decision live_bot_modified must be false")
    if plan.get("mode") != "precreation_manual":
        errors.append("precreation plan mode must be precreation_manual")
    if plan.get("manual_approval_required") is not True:
        errors.append("plan manual_approval_required must be true")
    if plan.get("remote_write_executed") is not False:
        errors.append("plan remote_write_executed must be false")
    if plan.get("systemd_changes_planned") is not False:
        errors.append("plan systemd_changes_planned must be false")
    if plan.get("oracle_live_bot_modified") is not False:
        errors.append("plan oracle_live_bot_modified must be false")
    if plan.get("order_execution_allowed") is not False:
        errors.append("plan order_execution_allowed must be false")
    if not isinstance(plan.get("paths"), dict):
        errors.append("plan paths must be present")
    if errors:
        raise RuntimeError("; ".join(errors))


def build_creation_result_record(paths: dict[str, str]) -> dict[str, Any]:
    return {
        "creation_executed": False,
        "created_by": "<manual-operator>",
        "created_at": None,
        "paths_checked": {
            "outbox_dir": {"path": paths["outbox_dir"], "exists": None},
            "processed_dir": {"path": paths["processed_dir"], "exists": None},
            "failed_dir": {"path": paths["failed_dir"], "exists": None},
            "state_dir": {"path": paths["state_dir"], "exists": None},
        },
        "remote_write_executed": False,
        "systemd_changed": False,
        "live_bot_modified": False,
        "order_execution_allowed": False,
        "result_status": "incomplete",
    }


def header(title: str) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        f"echo \"{title}\"\n"
        "echo \"Manual review packet only. GO is not deployment approval.\"\n"
        "echo \"No systemd operations. No live bot changes. No broker API. No orders. order_execution_allowed=false.\"\n\n"
    )


def render_manual_creation_commands(paths: dict[str, str]) -> str:
    return header("Oracle outbox manual creation command candidates") + path_exports(paths) + "\n".join(
        [
            "echo \"Read this file on Oracle, then manually copy only approved commented commands.\"",
            "echo \"수동 승인 후 주석 해제: directory creation candidates are comments by default.\"",
            'test -d "${ORACLE_TRADING_DIR}"',
            'ls -la "${ORACLE_TRADING_DIR}"',
            '# 수동 승인 후 주석 해제: mkdir -p "${AI_COUNCIL_OUTBOX_DIR}"',
            '# 수동 승인 후 주석 해제: mkdir -p "${AI_COUNCIL_PROCESSED_DIR}"',
            '# 수동 승인 후 주석 해제: mkdir -p "${AI_COUNCIL_FAILED_DIR}"',
            '# 수동 승인 후 주석 해제: mkdir -p "${AI_COUNCIL_STATE_DIR}"',
            '# 수동 승인 후 주석 해제 필요 시만: chmod 750 "${AI_COUNCIL_OUTBOX_DIR}"',
            "# chown is not recommended and remains prohibited unless separately approved.",
            "echo \"This file does not create directories when executed as-is.\"",
            "",
        ]
    )


def render_post_creation_verify_commands(paths: dict[str, str]) -> str:
    return header("Oracle outbox post-creation read-only verification") + path_exports(paths) + "\n".join(
        [
            'test -d "${AI_COUNCIL_OUTBOX_DIR}"',
            'test -d "${AI_COUNCIL_PROCESSED_DIR}"',
            'test -d "${AI_COUNCIL_FAILED_DIR}"',
            'test -d "${AI_COUNCIL_STATE_DIR}"',
            'ls -la "${AI_COUNCIL_OUTBOX_DIR}"',
            'ls -la "${AI_COUNCIL_PROCESSED_DIR}"',
            'ls -la "${AI_COUNCIL_FAILED_DIR}"',
            'ls -la "${AI_COUNCIL_STATE_DIR}"',
            'stat "${AI_COUNCIL_OUTBOX_DIR}"',
            'df -h "${ORACLE_TRADING_DIR}"',
            "echo \"No sample signal file is created by verification.\"",
            "",
        ]
    )


def render_rollback_after_creation(paths: dict[str, str]) -> str:
    return header("Oracle outbox rollback notes after manual creation") + path_exports(paths) + "\n".join(
        [
            "echo \"Rollback defaults to stopping further rollout and preserving any outbox files.\"",
            "echo \"Remote deletion/move commands are comments only and require separate approval.\"",
            '# 별도 승인 전 실행 금지: rm -r "${AI_COUNCIL_OUTBOX_DIR}"',
            '# 별도 승인 전 실행 금지: rm -r "${AI_COUNCIL_PROCESSED_DIR}"',
            '# 별도 승인 전 실행 금지: rm -r "${AI_COUNCIL_FAILED_DIR}"',
            '# 별도 승인 전 실행 금지: rm -r "${AI_COUNCIL_STATE_DIR}"',
            '# 별도 승인 전 실행 금지: mv "${AI_COUNCIL_OUTBOX_DIR}" "<approved-archive-dir>"',
            "echo \"No active rm/rmdir/mv command is executed by this file.\"",
            "",
        ]
    )


def path_exports(paths: dict[str, str]) -> str:
    return (
        f"ORACLE_TRADING_DIR='{paths['trading_dir']}'\n"
        f"AI_COUNCIL_OUTBOX_DIR='{paths['outbox_dir']}'\n"
        f"AI_COUNCIL_PROCESSED_DIR='{paths['processed_dir']}'\n"
        f"AI_COUNCIL_FAILED_DIR='{paths['failed_dir']}'\n"
        f"AI_COUNCIL_STATE_DIR='{paths['state_dir']}'\n\n"
    )


def render_manual_creation_checklist(paths: dict[str, str]) -> str:
    return f"""# Oracle Outbox Manual Creation Checklist

- [ ] Phase 24O GO decision reviewed; GO is not deployment approval.
- [ ] Oracle read-only precheck result reviewed.
- [ ] Outbox path approved: `{paths['outbox_dir']}`
- [ ] Processed path approved: `{paths['processed_dir']}`
- [ ] Failed path approved: `{paths['failed_dir']}`
- [ ] State path approved: `{paths['state_dir']}`
- [ ] Disk and Python environment checked.
- [ ] Directory creation commands remain commented until a human manually approves them.
- [ ] No `systemctl` start/stop/restart/reload command will be used.
- [ ] `penny_stock_bot.py` will not be modified in this step.
- [ ] No sample signal file will be created during verification.
- [ ] Rollback plan reviewed; remote deletion/move is not automatic.
- [ ] 실제 주문 없음, 브로커 API 연결 없음, `order_execution_allowed=false`.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
"""


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
        (ROOT / "tmp" / "oracle_outbox_manual_creation").resolve(),
        (MANUAL_DIR / "output").resolve(),
    ]
    if not any(output == root or output.is_relative_to(root) for root in allowed_roots):
        raise RuntimeError(f"refusing to remove non-generated output directory: {output}")


def run_command_review(packet_dir: Path) -> dict[str, Any]:
    script = MANUAL_DIR / "review_creation_commands.py"
    result = subprocess.run(
        [sys.executable, str(script), "--packet", str(packet_dir)],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command review did not return JSON: {result.stdout[:200]}") from exc
    if result.returncode != 0 and payload.get("status") == "passed":
        payload["status"] = "failed"
    return payload


def run_verify(packet_dir: Path) -> dict[str, Any]:
    script = MANUAL_DIR / "verify_manual_creation_packet.py"
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


def file_entry(path: Path, relative: Path, source: str) -> dict[str, Any]:
    return {
        "path": str(relative),
        "source": source,
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
