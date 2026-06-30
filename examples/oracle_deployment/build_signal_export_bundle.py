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
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_signal_export_bundle"
DEPLOYMENT_DIR = ROOT / "examples" / "oracle_deployment"
TEMPLATES_DIR = DEPLOYMENT_DIR / "templates"

SOURCE_FILES = [
    (
        ROOT / "examples" / "oracle_sidecar" / "patch_drafts" / "ai_council_signal_exporter_module.py",
        Path("ai_council_signal_exporter_module.py"),
    ),
    (
        ROOT / "examples" / "oracle_sidecar" / "us_trader_signal_outbox_bridge.py",
        Path("us_trader_signal_outbox_bridge.py"),
    ),
    (
        ROOT / "examples" / "external_bot" / "mapping_profiles" / "us_trader_oracle_v1.json",
        Path("mapping_profiles/us_trader_oracle_v1.json"),
    ),
    (
        ROOT / "examples" / "oracle_sidecar" / "sample_outbox" / "us_trader_signal_001.json",
        Path("sample_outbox/us_trader_signal_001.json"),
    ),
    (
        ROOT / "examples" / "oracle_sidecar" / "sample_outbox" / "us_trader_signal_order_like.json",
        Path("sample_outbox/us_trader_signal_order_like.json"),
    ),
    (
        ROOT / "examples" / "oracle_sidecar" / "sample_outbox" / "us_trader_signal_high_risk.json",
        Path("sample_outbox/us_trader_signal_high_risk.json"),
    ),
    (TEMPLATES_DIR / "deployment_bundle_README.md", Path("README.md")),
    (TEMPLATES_DIR / "oracle_env.example", Path("oracle_env.example")),
    (TEMPLATES_DIR / "manual_apply_commands.example.sh", Path("manual_apply_commands.example.sh")),
    (TEMPLATES_DIR / "sidecar_systemd_example.service", Path("sidecar_systemd_example.service")),
    (TEMPLATES_DIR / "sidecar_cron_example.txt", Path("sidecar_cron_example.txt")),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local Oracle signal export deployment bundle.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Bundle output directory.")
    parser.add_argument("--force", action="store_true", help="Replace an existing ignored/generated output directory.")
    parser.add_argument("--verify", action="store_true", help="Run bundle verification after build.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    try:
        result = build_bundle(Path(args.output), force=args.force)
        if args.verify:
            verify_result = run_verify(Path(args.output), pretty=False)
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


def build_bundle(output_dir: Path, *, force: bool = False) -> dict[str, Any]:
    output = output_dir.expanduser().resolve()
    reset_output_dir(output, force=force)
    output.mkdir(parents=True, exist_ok=True)

    copied_files: list[dict[str, Any]] = []
    for source, relative in SOURCE_FILES:
        if not source.exists():
            raise FileNotFoundError(f"required bundle source missing: {source}")
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
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
        "bundle_name": "oracle_signal_export_bundle",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bundle_path": str(output),
        "files": copied_files,
        "file_count": len(copied_files),
        "manual_approval_required": True,
        "oracle_server_contacted": False,
        "oracle_live_bot_modified": False,
        "oracle_systemd_touched": False,
        "broker_api_connected": False,
        "order_execution_allowed": False,
        "simulation_only": True,
        "safety_notes": [
            "Bundle generation is local only.",
            "Do not copy to Oracle or change systemd without separate manual approval.",
            "Keep sidecar bridge in preview mode for first verification.",
            "AI Council does not execute trades or connect to broker APIs.",
        ],
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "status": "ok",
        "bundle_path": str(output),
        "manifest_path": str(manifest_path),
        "file_count": len(copied_files),
        "manual_approval_required": True,
        "oracle_server_contacted": False,
        "order_execution_allowed": False,
    }


def reset_output_dir(output: Path, *, force: bool) -> None:
    if not output.exists():
        return
    if not output.is_dir():
        raise RuntimeError(f"output exists and is not a directory: {output}")
    if any(output.iterdir()) and not force:
        raise RuntimeError(f"output directory is not empty; pass --force for generated bundle output: {output}")
    if force:
        ensure_generated_output_path(output)
        shutil.rmtree(output)


def ensure_generated_output_path(output: Path) -> None:
    allowed_roots = [
        (ROOT / "tmp").resolve(),
        (ROOT / "deployment_bundles").resolve(),
        (DEPLOYMENT_DIR / "output").resolve(),
        (DEPLOYMENT_DIR / "bundles").resolve(),
    ]
    if not any(output == root or output.is_relative_to(root) for root in allowed_roots):
        raise RuntimeError(f"refusing to remove non-generated output directory: {output}")


def safe_source_label(source: Path) -> str:
    try:
        return str(source.resolve().relative_to(ROOT))
    except ValueError:
        return source.name


def run_verify(bundle: Path, *, pretty: bool) -> dict[str, Any]:
    script = DEPLOYMENT_DIR / "verify_signal_export_bundle.py"
    command = [sys.executable, str(script), "--bundle", str(bundle)]
    if pretty:
        command.append("--pretty")
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"verify did not return JSON: {result.stdout[:200]}") from exc
    if result.returncode != 0 and payload.get("status") == "ok":
        payload["status"] = "failed"
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
