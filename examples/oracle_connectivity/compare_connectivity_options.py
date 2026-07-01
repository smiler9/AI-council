#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any


SAFETY_BOUNDARY = (
    "AI Council does not execute trades or connect to broker APIs. "
    "This output is for review, risk analysis, and decision support only."
)


OPTIONS: list[dict[str, Any]] = [
    {
        "id": "oracle_outbox_only_preview",
        "label": "F. Oracle local JSON outbox only",
        "description": "Oracle accumulates signal JSON locally; AI Council integration happens later/manual.",
        "scores": {
            "safety": 10,
            "operational_complexity": 2,
            "security_exposure": 1,
            "reliability": 8,
            "preview_fit": 10,
            "paper_mode_fit": 5,
            "live_trading_risk": 1,
        },
        "rank": "1순위",
        "recommendation": "Use first for preview-only readiness because it creates no network exposure.",
    },
    {
        "id": "mac_pull_oracle_outbox",
        "label": "E. Mac AI Council pulls Oracle outbox read-only",
        "description": "Mac pulls approved outbox files from Oracle over a separately approved read-only workflow.",
        "scores": {
            "safety": 9,
            "operational_complexity": 4,
            "security_exposure": 2,
            "reliability": 7,
            "preview_fit": 9,
            "paper_mode_fit": 8,
            "live_trading_risk": 1,
        },
        "rank": "2순위",
        "recommendation": "Best next step after outbox-only if automated review is needed without public exposure.",
    },
    {
        "id": "ssh_reverse_tunnel_preview",
        "label": "C. SSH reverse tunnel from Mac to Oracle",
        "description": "Mac exposes local AI Council backend to Oracle through a reverse tunnel.",
        "scores": {
            "safety": 6,
            "operational_complexity": 6,
            "security_exposure": 4,
            "reliability": 5,
            "preview_fit": 7,
            "paper_mode_fit": 7,
            "live_trading_risk": 2,
        },
        "rank": "3순위",
        "recommendation": "Useful for temporary preview, but macOS sleep and tunnel supervision are operational risks.",
    },
    {
        "id": "oracle_local_ai_council_preview",
        "label": "D. Deploy AI Council backend on Oracle",
        "description": "Run AI Council backend or minimal preview receiver on Oracle.",
        "scores": {
            "safety": 7,
            "operational_complexity": 7,
            "security_exposure": 3,
            "reliability": 8,
            "preview_fit": 6,
            "paper_mode_fit": 8,
            "live_trading_risk": 2,
        },
        "rank": "보류",
        "recommendation": "Defer until preview payload flow is proven; it expands deployment scope.",
    },
    {
        "id": "cloudflare_tunnel_preview",
        "label": "B. Cloudflare/ngrok/Tailscale tunnel",
        "description": "Expose local Mac AI Council via a managed tunnel.",
        "scores": {
            "safety": 5,
            "operational_complexity": 6,
            "security_exposure": 6,
            "reliability": 7,
            "preview_fit": 6,
            "paper_mode_fit": 6,
            "live_trading_risk": 3,
        },
        "rank": "보류",
        "recommendation": "Convenient but requires tunnel credentials, access control, and logging discipline.",
    },
    {
        "id": "direct_mac_public_webhook",
        "label": "A. Oracle calls public Mac webhook directly",
        "description": "Expose the Mac backend directly to Oracle over a public address/port.",
        "scores": {
            "safety": 3,
            "operational_complexity": 7,
            "security_exposure": 9,
            "reliability": 4,
            "preview_fit": 4,
            "paper_mode_fit": 5,
            "live_trading_risk": 4,
        },
        "rank": "비추천",
        "recommendation": "Avoid direct public exposure of the local Mac backend.",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Oracle-to-AI Council connectivity options without network changes.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()
    payload = compare_options()
    print_json(payload, pretty=args.pretty)
    return 0


def compare_options() -> dict[str, Any]:
    ranked = sorted(OPTIONS, key=score_option, reverse=True)
    return {
        "status": "ok",
        "recommended_option": ranked[0]["id"],
        "reason": (
            "Outbox-only preview has the smallest network exposure and keeps Oracle live trading paths fully separated. "
            "Mac pull is the next safest automation step."
        ),
        "priority": {
            "1순위": "oracle_outbox_only_preview",
            "2순위": "mac_pull_oracle_outbox",
            "3순위": "ssh_reverse_tunnel_preview",
            "보류": ["oracle_local_ai_council_preview", "cloudflare_tunnel_preview"],
            "비추천": "direct_mac_public_webhook",
        },
        "options": ranked,
        "network_changes_performed": False,
        "tunnel_started": False,
        "ssh_executed": False,
        "order_execution_allowed": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }


def score_option(option: dict[str, Any]) -> int:
    scores = option["scores"]
    return (
        scores["safety"] * 3
        + (10 - scores["operational_complexity"]) * 2
        + (10 - scores["security_exposure"]) * 3
        + scores["reliability"]
        + scores["preview_fit"] * 2
        + scores["paper_mode_fit"]
        + (10 - scores["live_trading_risk"]) * 3
    )


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
