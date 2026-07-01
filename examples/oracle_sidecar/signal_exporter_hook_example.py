#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


"""
Reference-only helper for a future US Trader Oracle signal export hook.

Do not auto-apply this file to the Oracle live bot. This helper only shows how a
candidate signal dictionary could be exported to an outbox JSON file for AI
Council review. It must not be connected to broker APIs, live service control,
or position-changing logic.
"""


def build_ai_council_signal(
    *,
    symbol: str,
    signal: str,
    raw_side: str | None = None,
    price: float | None = None,
    volume: int | None = None,
    timeframe: str | None = None,
    indicators: dict | None = None,
    risk: dict | None = None,
    headlines: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    """Build a review-only AI Council signal payload."""

    timestamp = datetime.now(timezone.utc).isoformat()
    clean_symbol = symbol.strip().upper()
    return {
        "source": "us_trader_oracle",
        "signal_id": f"us_trader_{clean_symbol}_{uuid4().hex[:12]}",
        "symbol": clean_symbol,
        "signal": signal.strip() or "scanner_candidate",
        "action": (raw_side or "watch").strip().lower(),
        "price": price,
        "volume": volume,
        "timeframe": timeframe,
        "indicators": indicators or {},
        "news": headlines or [],
        "risk": risk or {},
        "timestamp": timestamp,
        "notes": notes or "Review-only signal export for AI Council.",
        "order_execution_allowed": False,
        "review_only": True,
        "simulation_only": True,
    }


def export_ai_council_signal(signal_payload: dict, outbox_dir: str | Path) -> Path:
    """Atomically write a signal payload to an outbox directory as JSON."""

    outbox = Path(outbox_dir)
    outbox.mkdir(parents=True, exist_ok=True)
    signal_id = str(signal_payload.get("signal_id") or uuid4().hex)
    target = outbox / f"{safe_filename(signal_id)}.json"
    temp = target.with_suffix(".json.tmp")
    payload = {
        **signal_payload,
        "order_execution_allowed": False,
        "review_only": True,
        "simulation_only": True,
    }
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temp.replace(target)
    return target


def safe_filename(value: str) -> str:
    allowed = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            allowed.append(char)
        else:
            allowed.append("_")
    filename = "".join(allowed).strip("._")
    return filename or f"signal_{uuid4().hex[:12]}"


if __name__ == "__main__":
    example = build_ai_council_signal(
        symbol="TESTA",
        signal="breakout",
        raw_side="buy",
        price=0.82,
        volume=12500000,
        timeframe="1m",
        indicators={"rsi": 68, "relative_volume": 5.2},
        risk={"spread_pct": 3.2, "premarket": False},
        headlines=["TESTA sample sidecar export headline"],
        notes="Example only. This does not execute trades.",
    )
    print(json.dumps(example, indent=2, sort_keys=True))
