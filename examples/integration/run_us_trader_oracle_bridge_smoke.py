#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
SECRET_HEADER = "X-AI-Council-Webhook-Secret"
PROFILE = "us_trader_oracle_v1"
PAYLOAD_DIR = Path(__file__).resolve().parents[1] / "external_bot" / "sample_payloads"
SAMPLE_FILES = [
    "us_trader_oracle_signal.json",
    "us_trader_oracle_order_like_signal.json",
    "us_trader_oracle_minimal_signal.json",
    "us_trader_oracle_high_risk_signal.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test the US Trader Oracle read-only bridge compatibility path."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("AI_COUNCIL_BASE_URL", DEFAULT_BASE_URL),
        help=f"AI Council base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--secret",
        default=os.getenv("AI_COUNCIL_WEBHOOK_SECRET"),
        help="Webhook secret for optional trade-signal review mode.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "30")),
    )
    parser.add_argument("--include-review", action="store_true", help="Also test trade-signal if webhooks are configured.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print final summary JSON.")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    steps: list[dict[str, Any]] = []
    try:
        health = get_json(f"{base_url}/health", args.timeout)
        assert_false(health, "health")
        steps.append({"name": "health", "status": health.get("status")})

        diagnostics = get_json(f"{base_url}/api/diagnostics/summary", args.timeout)
        assert_false(diagnostics, "diagnostics")
        steps.append({"name": "diagnostics", "status": diagnostics.get("status")})

        webhook_status = get_json(f"{base_url}/api/webhooks/status", args.timeout)
        steps.append(
            {
                "name": "webhook_status",
                "enabled": webhook_status.get("enabled"),
                "configured": webhook_status.get("configured"),
            }
        )

        preview_results = []
        for filename in SAMPLE_FILES:
            payload = load_payload(filename)
            request_body = {"profile": PROFILE, "payload": payload}
            response = post_json(f"{base_url}/api/webhooks/normalize-preview", request_body, None, args.timeout)
            validate_preview_response(filename, response)
            preview_results.append(
                {
                    "file": filename,
                    "ticker": response["normalized_payload"].get("ticker"),
                    "warnings": response.get("adapter_warnings", []),
                }
            )

        review_result = {"status": "skipped", "reason": "include-review was not requested"}
        if args.include_review:
            if not webhook_status.get("configured"):
                review_result = {
                    "status": "skipped",
                    "reason": webhook_status.get("disabled_reason") or "webhooks not configured",
                }
            elif webhook_status.get("require_secret") and not args.secret:
                review_result = {"status": "skipped", "reason": "AI_COUNCIL_WEBHOOK_SECRET is required"}
            else:
                payload = load_payload("us_trader_oracle_signal.json")
                request_body = {"profile": PROFILE, "payload": payload}
                response = post_json(
                    f"{base_url}/api/webhooks/trade-signal",
                    request_body,
                    args.secret,
                    args.timeout,
                )
                if response.get("order_execution_allowed") is not False:
                    raise RuntimeError("trade-signal response did not keep order_execution_allowed=false")
                review_result = {
                    "status": response.get("status"),
                    "duplicated": response.get("duplicated"),
                    "trade_review_id": (response.get("trade_review") or {}).get("id"),
                }

        summary = {
            "status": "passed",
            "profile": PROFILE,
            "preview_count": len(preview_results),
            "preview_results": preview_results,
            "review_mode": review_result,
            "safety": {
                "order_execution_allowed_all_false": True,
                "normalize_preview_created_trade_review": False,
                "broker_api_used": False,
                "oracle_live_bot_touched": False,
            },
            "steps": steps,
        }
    except Exception as exc:
        summary = {
            "status": "failed",
            "error": str(exc),
            "safety": {
                "broker_api_used": False,
                "oracle_live_bot_touched": False,
            },
            "steps": steps,
        }
        print_json(summary, pretty=args.pretty)
        return 1

    print_json(summary, pretty=args.pretty)
    return 0


def load_payload(filename: str) -> dict[str, Any]:
    path = PAYLOAD_DIR / filename
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"{filename}: expected JSON object")
    return payload


def validate_preview_response(filename: str, response: dict[str, Any]) -> None:
    if response.get("status") != "preview":
        raise RuntimeError(f"{filename}: expected status=preview")
    if response.get("order_execution_allowed") is not False:
        raise RuntimeError(f"{filename}: expected order_execution_allowed=false")
    if response.get("trade_review_created") is not False:
        raise RuntimeError(f"{filename}: normalize-preview must not create a trade review")
    normalized = response.get("normalized_payload") or {}
    if normalized.get("order_execution_allowed") is not False:
        raise RuntimeError(f"{filename}: normalized payload must keep order_execution_allowed=false")
    if filename == "us_trader_oracle_order_like_signal.json":
        warnings = " ".join(response.get("adapter_warnings") or [])
        if "order-like fields ignored for safety" not in warnings:
            raise RuntimeError(f"{filename}: missing order-like safety warning")


def get_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    return send_request(request, timeout)


def post_json(url: str, payload: dict[str, Any], secret: str | None, timeout: float) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if secret:
        headers[SECRET_HEADER] = secret
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    return send_request(request, timeout)


def send_request(request: urllib.request.Request, timeout: float) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"connection failed: {exc.reason}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("expected JSON object response")
    return data


def assert_false(payload: dict[str, Any], label: str) -> None:
    if payload.get("order_execution_allowed") is True:
        raise RuntimeError(f"{label}: order_execution_allowed must not be true")


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
