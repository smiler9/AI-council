#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_connectivity_plan.json"
DEFAULT_OPTION = "oracle_outbox_only_preview"
SAFETY_BOUNDARY = (
    "AI Council does not execute trades or connect to broker APIs. "
    "This output is for review, risk analysis, and decision support only."
)


PLANS: dict[str, dict[str, Any]] = {
    "oracle_outbox_only_preview": {
        "network_changes_required": False,
        "oracle_file_write_required": True,
        "ai_council_public_exposure_required": False,
        "risk_level": "low",
        "steps": [
            "Keep Oracle disconnected from AI Council network endpoints.",
            "After separate manual approval, allow Oracle to write TEST/review-only signal JSON to an outbox directory.",
            "Inspect JSON manually or use a separately approved Mac pull workflow.",
        ],
        "rollback": [
            "Stop any manually started preview sidecar process.",
            "Preserve outbox and state files for audit.",
            "Remove only preview sidecar files after manual approval.",
        ],
    },
    "mac_pull_oracle_outbox": {
        "network_changes_required": False,
        "oracle_file_write_required": True,
        "ai_council_public_exposure_required": False,
        "risk_level": "low_medium",
        "steps": [
            "Oracle writes JSON signals to an approved outbox directory.",
            "Mac pulls outbox files using a separately approved read-only SSH/SFTP workflow.",
            "AI Council processes pulled files with normalize-preview before any review mode.",
        ],
        "rollback": [
            "Stop the Mac pull job.",
            "Keep remote outbox files untouched.",
            "Remove local pulled copies if needed after audit.",
        ],
    },
    "ssh_reverse_tunnel_preview": {
        "network_changes_required": True,
        "oracle_file_write_required": True,
        "ai_council_public_exposure_required": False,
        "risk_level": "medium",
        "steps": [
            "Mac creates a reverse tunnel to Oracle after manual approval.",
            "Oracle sidecar calls the forwarded localhost port in preview mode.",
            "Monitor tunnel health; macOS sleep may break connectivity.",
        ],
        "rollback": [
            "Terminate the tunnel process.",
            "Keep sidecar in preview mode.",
            "Do not change Oracle live bot services.",
        ],
    },
    "cloudflare_tunnel_preview": {
        "network_changes_required": True,
        "oracle_file_write_required": True,
        "ai_council_public_exposure_required": True,
        "risk_level": "medium_high",
        "steps": [
            "Configure a managed tunnel only after token/security review.",
            "Require webhook secret and access controls.",
            "Use normalize-preview first; do not enable review mode by default.",
        ],
        "rollback": [
            "Disable the tunnel in the provider dashboard.",
            "Rotate tunnel credentials if exposed.",
            "Keep AI Council backend private again.",
        ],
    },
    "oracle_local_ai_council_preview": {
        "network_changes_required": False,
        "oracle_file_write_required": True,
        "ai_council_public_exposure_required": False,
        "risk_level": "medium",
        "steps": [
            "Deploy a read-only AI Council backend or minimal receiver on Oracle after separate approval.",
            "Use Oracle-local endpoint for sidecar preview mode.",
            "Maintain database, logs, backups, and process supervision separately.",
        ],
        "rollback": [
            "Stop the AI Council preview receiver after approval.",
            "Preserve logs and reports.",
            "Do not touch US Trader live services.",
        ],
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a preview-only Oracle connectivity plan.")
    parser.add_argument("--option", default=DEFAULT_OPTION, choices=sorted(PLANS), help="Connectivity option.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Ignored output plan JSON path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    try:
        result = generate_plan(args.option, Path(args.output))
    except Exception as exc:
        result = {
            "status": "failed",
            "error": str(exc),
            "network_changes_performed": False,
            "order_execution_allowed": False,
        }
        print_json(result, pretty=args.pretty)
        return 1
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def generate_plan(option: str, output_path: Path) -> dict[str, Any]:
    base = PLANS[option]
    plan = {
        "status": "ok",
        "option": option,
        "mode": "preview",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manual_approval_required": True,
        "network_changes_required": base["network_changes_required"],
        "network_changes_performed": False,
        "oracle_file_write_required": base["oracle_file_write_required"],
        "oracle_file_write_performed": False,
        "ai_council_public_exposure_required": base["ai_council_public_exposure_required"],
        "ai_council_public_exposure_created": False,
        "tunnel_started": False,
        "ssh_executed": False,
        "risk_level": base["risk_level"],
        "oracle_target": {
            "host": "<oracle-host>",
            "user": "<oracle-user>",
            "trading_dir": "<oracle-trading-dir>",
            "outbox_dir": "<oracle-outbox-dir>",
        },
        "ai_council_endpoint": "<ai-council-base-url>",
        "steps": base["steps"],
        "rollback": base["rollback"],
        "order_execution_allowed": False,
        "simulation_only": True,
        "safety_boundary": SAFETY_BOUNDARY,
    }
    output = output_path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "plan_path": str(output),
        "option": option,
        "mode": "preview",
        "manual_approval_required": True,
        "network_changes_performed": False,
        "order_execution_allowed": False,
    }


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
