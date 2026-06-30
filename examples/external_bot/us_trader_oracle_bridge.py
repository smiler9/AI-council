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
DEFAULT_PROFILE = "us_trader_oracle_v1"
SECRET_HEADER = "X-AI-Council-Webhook-Secret"
PROFILE_DIR = Path(__file__).resolve().parent / "mapping_profiles"

SAFE_SIDE_VALUES = {"review_only", "watch_only", "observe", "monitor"}
ORDER_SIDE_VALUES = {"buy", "sell", "long", "short", "entry", "exit", "order"}
ORDER_LIKE_FIELDS = {
    "order_id",
    "order_type",
    "quantity",
    "qty",
    "shares",
    "notional",
    "take_profit",
    "stop_loss",
    "broker",
    "account",
    "route",
    "tif",
    "extended_hours",
    "submit" + "_order",
    "place" + "_order",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only bridge for sending US Trader Oracle signal payloads to AI Council "
            "normalize-preview or trade-signal review endpoints."
        )
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--payload", help="Path to a JSON payload file.")
    input_group.add_argument("--stdin", action="store_true", help="Read JSON payload from stdin.")
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        choices=["generic", "penny_bot_v1", "minimal_signal", "us_trader_oracle_v1"],
        help=f"Mapping profile. Default: {DEFAULT_PROFILE}",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--preview",
        action="store_true",
        help="Call /api/webhooks/normalize-preview. This is the default mode.",
    )
    mode_group.add_argument(
        "--review",
        action="store_true",
        help="Call /api/webhooks/trade-signal to create a read-only AI Council review.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the request body without HTTP calls.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("AI_COUNCIL_BASE_URL", DEFAULT_BASE_URL),
        help=f"AI Council base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--secret",
        default=os.getenv("AI_COUNCIL_WEBHOOK_SECRET"),
        help="Webhook secret. Defaults to AI_COUNCIL_WEBHOOK_SECRET.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "30")),
        help="Request timeout in seconds.",
    )
    args = parser.parse_args()

    try:
        raw_payload = read_payload(Path(args.payload)) if args.payload else read_stdin_payload()
        profile = load_profile(args.profile)
        request_body = {
            "profile": profile["name"],
            "payload": raw_payload,
        }
        if args.dry_run:
            response = {
                "status": "dry_run",
                "mode": "review" if args.review else "preview",
                "profile": profile["name"],
                "request_body": request_body,
                "normalized_preview": build_local_preview(raw_payload, profile),
                "webhook_called": False,
                "broker_api_called": False,
                "order_execution_allowed": False,
            }
        else:
            endpoint = "/api/webhooks/trade-signal" if args.review else "/api/webhooks/normalize-preview"
            response = post_json(
                f"{args.base_url.rstrip('/')}{endpoint}",
                request_body,
                args.secret,
                args.timeout,
            )
    except Exception as exc:
        print(f"US Trader Oracle bridge failed: {exc}", file=sys.stderr)
        return 1

    print_json(response, pretty=args.pretty)
    return 0


def read_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"payload file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return require_object(json.load(handle))


def read_stdin_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("stdin payload is empty")
    return require_object(json.loads(raw))


def require_object(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("payload JSON must be an object")
    return data


def load_profile(name: str) -> dict[str, Any]:
    path = PROFILE_DIR / f"{name}.json"
    with path.open("r", encoding="utf-8") as handle:
        profile = json.load(handle)
    if not isinstance(profile.get("fields"), dict):
        raise ValueError(f"invalid mapping profile: {path}")
    return profile


def build_local_preview(raw_payload: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    mapped = apply_profile(raw_payload, profile)
    raw_side = str(mapped.get("side") or "").strip().lower()
    side = raw_side if raw_side in SAFE_SIDE_VALUES else "review_only"
    warnings = []
    order_like = sorted(key for key in raw_payload if key in ORDER_LIKE_FIELDS)
    if order_like:
        warnings.append("order-like fields ignored for safety: " + ", ".join(order_like))
    if raw_side in ORDER_SIDE_VALUES:
        warnings.append(f"buy/sell side was treated as review context only: {raw_side}")
    elif raw_side and raw_side not in SAFE_SIDE_VALUES:
        warnings.append(f"unsupported side value treated as review context only: {raw_side}")
    if not mapped.get("ticker"):
        warnings.append("missing ticker")
    if not mapped.get("strategy_signal"):
        warnings.append("missing strategy_signal")
    if mapped.get("price") in {None, ""}:
        warnings.append("missing price")
    if mapped.get("volume") in {None, ""}:
        warnings.append("missing volume")
    if not mapped.get("news_headlines"):
        warnings.append("news data unavailable")
    return {
        "ticker": str(mapped.get("ticker") or "").upper() or None,
        "strategy_signal": mapped.get("strategy_signal"),
        "side": side,
        "raw_side": raw_side or None,
        "price": mapped.get("price"),
        "volume": mapped.get("volume"),
        "timeframe": mapped.get("timeframe"),
        "source": mapped.get("source"),
        "technical_indicators": mapped.get("technical_indicators") or {},
        "news_headlines": mapped.get("news_headlines") or [],
        "risk_context": mapped.get("risk_context") or {},
        "adapter_warnings": warnings,
        "order_execution_allowed": False,
        "review_only": True,
    }


def apply_profile(raw_payload: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    mapped = dict(raw_payload)
    for standard_field, aliases in profile["fields"].items():
        if standard_field in mapped and mapped[standard_field] is not None:
            continue
        for alias in aliases:
            if alias in raw_payload and raw_payload[alias] is not None:
                mapped[standard_field] = raw_payload[alias]
                break
    mapped.setdefault("source", profile.get("source") or profile["name"])
    mapped["bridge_profile"] = profile["name"]
    return mapped


def post_json(url: str, payload: dict[str, Any], secret: str | None, timeout: float) -> dict[str, Any]:
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


def decode_json_response(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI Council returned non-JSON response") from exc
    if not isinstance(data, dict):
        raise RuntimeError("AI Council returned JSON that is not an object")
    return data


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
