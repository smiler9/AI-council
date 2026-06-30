from __future__ import annotations

from pathlib import Path
from typing import Any

from .llm.config import LLMConfig
from .market_data import (
    MarketDataConfig,
    MarketDataProviderError,
    get_market_data_provider,
    safe_fallback_snapshot,
)
from .repository import create_ticker_review
from .schemas import TickerReviewCreate, TradeReviewCreate
from .trade_reviews import run_trade_review


SOURCE = "ticker_only_auto_research"


def run_ticker_review(
    payload: TickerReviewCreate,
    *,
    db_path: str | Path | None,
    report_dir: str | Path | None,
    llm_config: LLMConfig,
    market_data_config: MarketDataConfig,
    market_data_override: dict[str, Any] | None = None,
    source: str = SOURCE,
) -> dict:
    ticker = payload.ticker.strip().upper()
    timeframe = payload.timeframe.strip() or "1d"
    provider = get_market_data_provider(market_data_config)
    try:
        market_data = market_data_override or provider.snapshot(
            ticker,
            review_mode=payload.review_mode,
            timeframe=timeframe,
        )
    except (MarketDataProviderError, RuntimeError, ValueError) as exc:
        market_data = safe_fallback_snapshot(ticker, provider_name=provider.name)
        market_data["notes"] = f"{market_data['notes']} Error: {exc}"
    provider_name = str(market_data.get("provider") or provider.name)
    auto_payload = build_auto_research_payload(
        payload=payload,
        market_data=market_data,
        provider_name=provider_name,
        timeout_seconds=market_data_config.timeout_seconds,
        source=source,
    )
    result = run_trade_review(
        TradeReviewCreate(**auto_payload),
        db_path=db_path,
        report_dir=report_dir,
        llm_config=llm_config,
    )
    structured_decision = result["structured_decision"]
    review = result["trade_review"]
    ticker_review = create_ticker_review(
        ticker=ticker,
        review_mode=payload.review_mode,
        timeframe=timeframe,
        source=source,
        auto_payload=auto_payload,
        trade_review_id=review["id"],
        linked_meeting_id=review["linked_meeting_id"],
        decision=structured_decision["decision"],
        risk_level=structured_decision["risk_level"],
        db_path=db_path,
    )
    return {
        "ticker_review": ticker_review,
        "market_data": market_data,
        **result,
        "order_execution_allowed": False,
    }


def build_auto_research_payload(
    *,
    payload: TickerReviewCreate,
    market_data: dict[str, Any],
    provider_name: str,
    timeout_seconds: float = 10.0,
    source: str = SOURCE,
) -> dict[str, Any]:
    ticker = payload.ticker.strip().upper()
    timeframe = payload.timeframe.strip() or "1d"
    notes = (payload.notes or "Ticker-only auto research request").strip()
    technical_indicators = {}
    if market_data.get("relative_volume") is not None:
        technical_indicators["relative_volume"] = market_data["relative_volume"]
    risk_context = {
        "auto_research": True,
        "review_mode": payload.review_mode,
        "data_source": provider_name,
        "market_data_provider": provider_name,
        "market_data_available": bool(market_data.get("market_data_available")),
        "news_available": bool(market_data.get("news_available")),
        "data_quality": market_data.get("data_quality", "limited"),
        "provider_notes": market_data.get("notes"),
    }
    for key in ["spread_pct", "premarket", "relative_volume", "scan_reason"]:
        if market_data.get(key) is not None:
            risk_context[key] = market_data[key]
    if market_data.get("risk_context"):
        risk_context.update(market_data["risk_context"])
    risk_context["review_mode"] = payload.review_mode
    risk_context["timeframe"] = timeframe

    return {
        "ticker": ticker,
        "strategy_signal": "auto_research",
        "side": "review_only",
        "price": market_data.get("last_price"),
        "volume": market_data.get("volume"),
        "timeframe": timeframe,
        "source": source,
        "notes": notes,
        "technical_indicators": technical_indicators,
        "news_headlines": market_data.get("mock_news_headlines") or [],
        "risk_context": risk_context,
        "auto_research_metadata": {
            "requested_ticker": ticker,
            "review_mode": payload.review_mode,
            "timeframe": timeframe,
            "market_data_provider": provider_name,
            "market_data_timeout_seconds": timeout_seconds,
            "scan_reason": market_data.get("scan_reason"),
            "order_execution_allowed": False,
        },
        "order_execution_allowed": False,
        "review_only": True,
    }
