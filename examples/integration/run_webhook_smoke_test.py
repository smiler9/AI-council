#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = os.getenv("AI_COUNCIL_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
WEBHOOK_SECRET = os.getenv("AI_COUNCIL_WEBHOOK_SECRET")
TIMEOUT_SECONDS = float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "20"))
SECRET_HEADER = "X-AI-Council-Webhook-Secret"
PAYLOAD_DIR = Path(__file__).resolve().parents[1] / "external_bot" / "sample_payloads"


def main() -> int:
    try:
        health = get_json(f"{BASE_URL}/health")
        print(f"Backend health: {health.get('status')} ({health.get('service')})")

        status = get_json(f"{BASE_URL}/api/webhooks/status")
        print(
            "Webhook status: "
            f"enabled={status.get('enabled')} configured={status.get('configured')} "
            f"require_secret={status.get('require_secret')}"
        )
        if not status.get("configured"):
            print(f"Webhook smoke test skipped: {status.get('disabled_reason')}")
            return 0
        if status.get("require_secret") and not WEBHOOK_SECRET:
            print("Webhook smoke test failed: AI_COUNCIL_WEBHOOK_SECRET is required.", file=sys.stderr)
            return 1

        results = [
            send_payload("breakout_signal.json"),
            send_payload("high_spread_signal.json"),
            send_payload("missing_news_signal.json"),
            send_payload("duplicate_signal.json"),
        ]
        validate_results(results)
    except Exception as exc:
        print(f"Webhook smoke test failed: {exc}", file=sys.stderr)
        return 1

    print("\nSmoke test summary")
    for name, payload in results:
        review = payload.get("trade_review") or {}
        decision = payload.get("structured_decision") or review.get("structured_decision") or {}
        print(
            f"- {name}: status={payload.get('status')} duplicated={payload.get('duplicated')} "
            f"review={review.get('id')} decision={decision.get('decision')} "
            f"risk={decision.get('risk_level')} orders={payload.get('order_execution_allowed')}"
        )
    return 0


def send_payload(filename: str) -> tuple[str, dict]:
    payload = load_payload(filename)
    response = post_json(f"{BASE_URL}/api/webhooks/trade-signal", payload)
    assert_field(response.get("order_execution_allowed") is False, filename, "order_execution_allowed=false")
    review = response.get("trade_review")
    if not review:
        raise RuntimeError(f"{filename}: missing trade_review in response")
    decision = response.get("structured_decision") or review.get("structured_decision") or {}
    for field in ["decision", "risk_level"]:
        if not decision.get(field):
            raise RuntimeError(f"{filename}: missing structured_decision.{field}")
    if not review.get("id"):
        raise RuntimeError(f"{filename}: missing trade_review.id")
    return filename, response


def validate_results(results: list[tuple[str, dict]]) -> None:
    duplicate = dict(results)["duplicate_signal.json"]
    if duplicate.get("duplicated") is not True:
        raise RuntimeError("duplicate_signal.json did not return duplicated=true")
    breakout = dict(results)["breakout_signal.json"]
    if duplicate.get("trade_review", {}).get("id") != breakout.get("trade_review", {}).get("id"):
        raise RuntimeError("duplicate signal did not return the original trade_review.id")


def load_payload(filename: str) -> dict:
    path = PAYLOAD_DIR / filename
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"{filename}: payload must be a JSON object")
    return payload


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    return send_request(request)


def post_json(url: str, payload: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if WEBHOOK_SECRET:
        headers[SECRET_HEADER] = WEBHOOK_SECRET
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    return send_request(request)


def send_request(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return decode_json(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"connection failed: {exc.reason}") from exc


def decode_json(raw: bytes) -> dict:
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("expected JSON object response")
    return data


def assert_field(condition: bool, name: str, detail: str) -> None:
    if not condition:
        raise RuntimeError(f"{name}: expected {detail}")


if __name__ == "__main__":
    raise SystemExit(main())
