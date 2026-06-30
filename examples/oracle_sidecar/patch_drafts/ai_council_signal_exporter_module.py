from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


SOURCE = "us_trader_oracle"
DEFAULT_REVIEW_ONLY_SIDE = "review_only"


class SignalExportError(ValueError):
    """Raised when a signal export payload is unsafe or incomplete."""


def sanitize_symbol(symbol: str) -> str:
    clean = "".join(char for char in str(symbol).strip().upper() if char.isalnum() or char in {".", "-"})
    if not clean:
        raise SignalExportError("symbol is required")
    return clean[:16]


def make_signal_id(symbol: str, strategy_signal: str, timestamp: str | None = None) -> str:
    clean_symbol = sanitize_symbol(symbol)
    clean_strategy = "".join(
        char if char.isalnum() or char in {"_", "-"} else "_"
        for char in str(strategy_signal or "signal").strip().lower()
    ).strip("_") or "signal"
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{SOURCE}_{clean_symbol}_{clean_strategy}_{stamp}_{uuid4().hex[:8]}"


def build_ai_council_signal(
    *,
    symbol: str,
    strategy_signal: str,
    raw_side: str | None = None,
    price: float | None = None,
    volume: int | None = None,
    timeframe: str | None = None,
    indicators: dict | None = None,
    risk_context: dict | None = None,
    news_headlines: list[str] | None = None,
    notes: str | None = None,
    extra_context: dict | None = None,
) -> dict:
    """Build a review-only payload for AI Council outbox export."""

    timestamp = datetime.now(timezone.utc).isoformat()
    clean_symbol = sanitize_symbol(symbol)
    signal = str(strategy_signal or "scanner_candidate").strip() or "scanner_candidate"
    payload = {
        "source": SOURCE,
        "signal_id": make_signal_id(clean_symbol, signal),
        "symbol": clean_symbol,
        "signal": signal,
        "action": str(raw_side or "watch").strip().lower() or "watch",
        "price": _optional_float(price),
        "volume": _optional_int(volume),
        "timeframe": str(timeframe).strip() if timeframe else None,
        "indicators": indicators or {},
        "risk": risk_context or {},
        "news": news_headlines or [],
        "timestamp": timestamp,
        "notes": notes or "Review-only AI Council signal export.",
        "extra_context": extra_context or {},
        "review_only": True,
        "simulation_only": False,
        "order_execution_allowed": False,
    }
    validate_export_payload(payload)
    return payload


def validate_export_payload(payload: dict) -> bool:
    if not isinstance(payload, dict):
        raise SignalExportError("payload must be a dict")
    if payload.get("source") != SOURCE:
        raise SignalExportError("source must be us_trader_oracle")
    sanitize_symbol(str(payload.get("symbol") or ""))
    if not str(payload.get("signal") or "").strip():
        raise SignalExportError("signal is required")
    if payload.get("order_execution_allowed") is not False:
        raise SignalExportError("order_execution_allowed must be false")
    if payload.get("review_only") is not True:
        raise SignalExportError("review_only must be true")
    if _contains_order_intent(payload):
        warning = "order-like fields preserved as review context only"
        warnings = payload.setdefault("adapter_warnings", [])
        if warning not in warnings:
            warnings.append(warning)
    payload["order_execution_allowed"] = False
    return True


def export_ai_council_signal(payload: dict, outbox_dir: str | os.PathLike[str]) -> Path:
    """Atomically export one validated signal payload to an outbox JSON file."""

    validate_export_payload(payload)
    outbox = Path(outbox_dir)
    outbox.mkdir(parents=True, exist_ok=True)
    signal_id = _safe_filename(str(payload.get("signal_id") or uuid4().hex))
    target = outbox / f"{signal_id}.json"
    temp = target.with_suffix(".json.tmp")
    payload = {**payload, "order_execution_allowed": False, "review_only": True}
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temp.replace(target)
    return target


def _contains_order_intent(payload: dict) -> bool:
    order_like_fields = {
        "quantity",
        "qty",
        "shares",
        "order_type",
        "stop_loss",
        "take_profit",
        "broker",
        "account",
        "route",
        "tif",
    }
    return any(field in payload for field in order_like_fields)


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _safe_filename(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)
    return safe.strip("._") or f"signal_{uuid4().hex[:12]}"
