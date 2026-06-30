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


DEFAULT_WEBHOOK_URL = "http://127.0.0.1:8000/api/webhooks/trade-signal"
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
        description="Bridge an external bot JSON signal into AI Council's review-only webhook."
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--payload", help="Path to a JSON payload file.")
    input_group.add_argument("--stdin", action="store_true", help="Read JSON payload from stdin.")
    parser.add_argument(
        "--profile",
        default="generic",
        choices=["generic", "penny_bot_v1", "minimal_signal"],
        help="Payload mapping profile.",
    )
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print mapped review-only payload without calling the webhook.",
    )
    args = parser.parse_args()

    try:
        raw_payload = read_payload(Path(args.payload)) if args.payload else read_stdin_payload()
        profile = load_profile(args.profile)
        mapped_payload = apply_profile(raw_payload, profile)
        if args.dry_run:
            response = {
                "status": "dry_run",
                "profile": profile["name"],
                "normalized_preview": build_preview_payload(mapped_payload, raw_payload),
                "webhook_called": False,
                "order_execution_allowed": False,
            }
        else:
            response = post_json(args.url, mapped_payload, args.secret, args.timeout)
    except Exception as exc:
        print(f"AI Council bridge failed: {exc}", file=sys.stderr)
        return 1

    if args.pretty:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(json.dumps(response, sort_keys=True))
    return 0


def read_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"payload file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return require_object(data)


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


def apply_profile(raw_payload: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    mapped = dict(raw_payload)
    for standard_field, aliases in profile["fields"].items():
        if standard_field in mapped:
            continue
        value = first_present(raw_payload, aliases)
        if value is not None:
            mapped[standard_field] = value
    mapped.setdefault("source", raw_payload.get("source") or profile["name"])
    mapped.setdefault("notes", f"Bridge client mapped payload with profile {profile['name']}.")
    mapped["bridge_profile"] = profile["name"]
    return mapped


def first_present(payload: dict[str, Any], aliases: list[str]) -> Any:
    for key in aliases:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def build_preview_payload(mapped_payload: dict[str, Any], raw_payload: dict[str, Any]) -> dict[str, Any]:
    warnings = adapter_warnings(mapped_payload)
    raw_side = str(mapped_payload.get("side") or "").strip().lower()
    side = raw_side if raw_side in SAFE_SIDE_VALUES else "review_only"
    if raw_side in ORDER_SIDE_VALUES:
        warnings.append(f"buy/sell side was treated as review context only: {raw_side}")
    elif raw_side and raw_side not in SAFE_SIDE_VALUES:
        warnings.append(f"unsupported side value treated as review context only: {raw_side}")
    if not mapped_payload.get("ticker"):
        warnings.append("missing ticker")
    if not mapped_payload.get("strategy_signal"):
        warnings.append("missing strategy_signal")
    if mapped_payload.get("price") in {None, ""}:
        warnings.append("missing price")
    if mapped_payload.get("volume") in {None, ""}:
        warnings.append("missing volume")
    if not mapped_payload.get("news_headlines"):
        warnings.append("news data unavailable")

    return {
        "ticker": str(mapped_payload.get("ticker") or "").upper() or None,
        "strategy_signal": mapped_payload.get("strategy_signal"),
        "side": side,
        "raw_side": raw_side or None,
        "price": mapped_payload.get("price"),
        "volume": mapped_payload.get("volume"),
        "timeframe": mapped_payload.get("timeframe"),
        "source": mapped_payload.get("source"),
        "notes": mapped_payload.get("notes"),
        "technical_indicators": mapped_payload.get("technical_indicators") or {},
        "news_headlines": mapped_payload.get("news_headlines") or [],
        "risk_context": mapped_payload.get("risk_context") or {},
        "adapter_warnings": warnings,
        "input_payload_json": raw_payload,
        "order_execution_allowed": False,
    }


def adapter_warnings(payload: dict[str, Any]) -> list[str]:
    fields = sorted(key for key in payload if key in ORDER_LIKE_FIELDS)
    if not fields:
        return []
    return ["order-like fields ignored for safety: " + ", ".join(fields)]


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


if __name__ == "__main__":
    raise SystemExit(main())
