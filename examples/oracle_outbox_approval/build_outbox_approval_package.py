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
APPROVAL_DIR = ROOT / "examples" / "oracle_outbox_approval"
TEMPLATES_DIR = APPROVAL_DIR / "templates"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_outbox_approval"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)

SOURCE_FILES = [
    (TEMPLATES_DIR / "outbox_paths.example.json", Path("outbox_paths.example.json")),
    (TEMPLATES_DIR / "outbox_manual_checklist.md", Path("outbox_manual_checklist.md")),
    (TEMPLATES_DIR / "outbox_file_contract.md", Path("outbox_file_contract.md")),
    (TEMPLATES_DIR / "outbox_retention_policy.md", Path("outbox_retention_policy.md")),
    (TEMPLATES_DIR / "outbox_rollback_plan.md", Path("outbox_rollback_plan.md")),
    (TEMPLATES_DIR / "outbox_apply_commands.example.sh", Path("outbox_apply_commands.example.sh")),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local Oracle outbox approval package.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Ignored package output directory.")
    parser.add_argument("--force", action="store_true", help="Replace an existing generated package output.")
    parser.add_argument("--verify", action="store_true", help="Run package verification after build.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    try:
        result = build_package(Path(args.output), force=args.force)
        if args.verify:
            verify_result = run_verify(Path(args.output))
            result["verify"] = verify_result
            if verify_result.get("status") != "ok":
                result["status"] = "failed"
    except Exception as exc:
        result = {
            "status": "failed",
            "error": str(exc),
            "oracle_server_contacted": False,
            "order_execution_allowed": False,
        }
        print_json(result, pretty=args.pretty)
        return 1

    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def build_package(output_dir: Path, *, force: bool = False) -> dict[str, Any]:
    output = output_dir.expanduser().resolve()
    reset_output_dir(output, force=force)
    output.mkdir(parents=True, exist_ok=True)

    copied_files: list[dict[str, Any]] = []
    for source, relative in SOURCE_FILES:
        if not source.exists():
            raise FileNotFoundError(f"required package source missing: {source}")
        destination = output / relative
        shutil.copy2(source, destination)
        copied_files.append(
            {
                "path": str(relative),
                "source": safe_source_label(source),
                "sha256": sha256_file(destination),
                "size_bytes": destination.stat().st_size,
            }
        )

    manifest = {
        "status": "ok",
        "package_name": "oracle_outbox_approval_package",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_path": str(output),
        "files": copied_files,
        "file_count": len(copied_files),
        "manual_approval_required": True,
        "remote_delete": False,
        "remote_move": False,
        "oracle_server_contacted": False,
        "oracle_live_bot_modified": False,
        "oracle_systemd_touched": False,
        "broker_api_connected": False,
        "order_execution_allowed": False,
        "simulation_only": True,
        "safety_boundary": SAFETY_BOUNDARY,
        "safety_notes": [
            "Package generation is local only.",
            "Do not create Oracle directories or change permissions without separate manual approval.",
            "Mac pull remains read-only and does not delete or move remote files.",
            "AI Council does not execute trades or connect to broker APIs.",
        ],
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "status": "ok",
        "package_path": str(output),
        "manifest_path": str(manifest_path),
        "file_count": len(copied_files),
        "manual_approval_required": True,
        "remote_delete": False,
        "remote_move": False,
        "oracle_server_contacted": False,
        "order_execution_allowed": False,
    }


def reset_output_dir(output: Path, *, force: bool) -> None:
    if not output.exists():
        return
    if not output.is_dir():
        raise RuntimeError(f"output exists and is not a directory: {output}")
    if any(output.iterdir()) and not force:
        raise RuntimeError(f"output directory is not empty; pass --force for generated package output: {output}")
    if force:
        ensure_generated_output_path(output)
        shutil.rmtree(output)


def ensure_generated_output_path(output: Path) -> None:
    allowed_roots = [
        (ROOT / "tmp").resolve(),
        (ROOT / "outbox_approval_packages").resolve(),
        (APPROVAL_DIR / "output").resolve(),
        (APPROVAL_DIR / "packages").resolve(),
    ]
    if not any(output == root or output.is_relative_to(root) for root in allowed_roots):
        raise RuntimeError(f"refusing to remove non-generated output directory: {output}")


def run_verify(package_dir: Path) -> dict[str, Any]:
    script = APPROVAL_DIR / "verify_outbox_approval_package.py"
    result = subprocess.run(
        [sys.executable, str(script), "--package", str(package_dir)],
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
