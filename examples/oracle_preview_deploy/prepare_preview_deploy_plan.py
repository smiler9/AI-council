#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUNDLE = ROOT / "tmp" / "oracle_signal_export_bundle"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_preview_deploy_plan.json"
SAFETY_BOUNDARY = (
    "AI Council does not execute trades or connect to broker APIs. "
    "This output is for review, risk analysis, and decision support only."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a preview-only Oracle sidecar deployment plan.")
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE), help="Local deployment bundle directory.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Ignored output plan JSON path.")
    parser.add_argument("--oracle-user", default="<oracle-user>")
    parser.add_argument("--oracle-host", default="<oracle-host>")
    parser.add_argument("--oracle-trading-dir", default="<oracle-trading-dir>")
    parser.add_argument("--oracle-sidecar-dir", default="<oracle-sidecar-dir>")
    parser.add_argument("--ai-council-base-url", default="<ai-council-base-url>")
    parser.add_argument("--mode", default="preview", help="Must remain preview for Phase 24G.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    try:
        result = prepare_plan(
            bundle=Path(args.bundle),
            output=Path(args.output),
            oracle_user=args.oracle_user,
            oracle_host=args.oracle_host,
            oracle_trading_dir=args.oracle_trading_dir,
            oracle_sidecar_dir=args.oracle_sidecar_dir,
            ai_council_base_url=args.ai_council_base_url,
            mode=args.mode,
        )
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


def prepare_plan(
    *,
    bundle: Path,
    output: Path,
    oracle_user: str,
    oracle_host: str,
    oracle_trading_dir: str,
    oracle_sidecar_dir: str,
    ai_council_base_url: str,
    mode: str,
) -> dict[str, Any]:
    bundle_dir = bundle.expanduser().resolve()
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"bundle manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    created_at = datetime.now(timezone.utc).isoformat()
    plan_seed = f"{created_at}|{bundle_dir}|{oracle_user}|{oracle_host}|{oracle_sidecar_dir}|{mode}"
    plan_id = hashlib.sha256(plan_seed.encode("utf-8")).hexdigest()[:16]
    sidecar_dir = oracle_sidecar_dir.rstrip("/")
    outbox_dir = f"{sidecar_dir}/outbox"
    processed_dir = f"{sidecar_dir}/processed"
    failed_dir = f"{sidecar_dir}/failed"
    env_file_path = f"{sidecar_dir}/preview_sidecar.env"

    plan = {
        "status": "ok",
        "plan_id": f"oracle-preview-{plan_id}",
        "created_at": created_at,
        "mode": mode,
        "bundle_path": str(bundle_dir),
        "bundle_manifest_path": str(manifest_path),
        "bundle_file_count": manifest.get("file_count"),
        "oracle_target": {
            "user": oracle_user,
            "host": oracle_host,
            "trading_dir": oracle_trading_dir,
        },
        "ai_council_base_url": ai_council_base_url,
        "sidecar_dir": sidecar_dir,
        "outbox_dir": outbox_dir,
        "processed_dir": processed_dir,
        "failed_dir": failed_dir,
        "env_file_path": env_file_path,
        "run_once_command_preview": (
            f"cd {sidecar_dir} && python3 us_trader_signal_outbox_bridge.py "
            f"--mode preview --outbox {outbox_dir} --state {sidecar_dir}/state/preview_state.json --pretty"
        ),
        "verify_command_preview": (
            f"cd {sidecar_dir} && python3 us_trader_signal_outbox_bridge.py "
            f"--mode preview --outbox {sidecar_dir}/sample_outbox --dry-run --pretty"
        ),
        "rollback_command_preview": "manual approval required before removing preview sidecar files",
        "auto_start": False,
        "systemd_enabled": False,
        "manual_approval_required": True,
        "oracle_server_contacted": False,
        "oracle_files_written": False,
        "oracle_systemd_touched": False,
        "oracle_live_bot_modified": False,
        "simulation_only": True,
        "order_execution_allowed": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }
    output_path = output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "plan_path": str(output_path),
        "plan_id": plan["plan_id"],
        "mode": plan["mode"],
        "manual_approval_required": True,
        "oracle_server_contacted": False,
        "oracle_files_written": False,
        "order_execution_allowed": False,
    }


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
