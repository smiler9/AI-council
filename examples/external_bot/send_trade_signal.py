#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_WEBHOOK_URL = "http://127.0.0.1:8000/api/webhooks/trade-signal"
SECRET_HEADER = "X-AI-Council-Webhook-Secret"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send a read-only candidate trade signal to AI Council."
    )
    parser.add_argument("--payload", required=True, help="Path to a JSON payload file.")
    parser.add_argument(
        "--url",
        default=os.getenv("AI_COUNCIL_WEBHOOK_URL", DEFAULT_WEBHOOK_URL),
        help=f"Webhook URL. Default: {DEFAULT_WEBHOOK_URL}",
    )
    parser.add_argument(
        "--secret",
        default=os.getenv("AI_COUNCIL_WEBHOOK_SECRET"),
        help="Webhook secret. Defaults to AI_COUNCIL_WEBHOOK_SECRET.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "15")),
        help="Request timeout in seconds.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print response JSON.")
    args = parser.parse_args()

    try:
        payload = read_payload(Path(args.payload))
        response = post_json(args.url, payload, args.secret, args.timeout)
    except Exception as exc:
        print(f"AI Council webhook send failed: {exc}", file=sys.stderr)
        return 1

    if args.pretty:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(json.dumps(response, sort_keys=True))
    return 0


def read_payload(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"payload file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("payload JSON must be an object")
    return data


def post_json(url: str, payload: dict, secret: str | None, timeout: float) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if secret:
        headers[SECRET_HEADER] = secret
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return decode_json_response(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"connection failed: {exc.reason}") from exc


def decode_json_response(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI Council returned non-JSON response") from exc
    if not isinstance(data, dict):
        raise RuntimeError("AI Council returned JSON that is not an object")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
