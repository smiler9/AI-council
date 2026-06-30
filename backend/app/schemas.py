from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MeetingCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=240)
    ticker: str | None = Field(default=None, max_length=16)
    mode: Literal[
        "quick_review",
        "deep_debate",
        "skeptic_review",
        "risk_gate_review",
        "action_plan",
    ] = "quick_review"


class MeetingRunResponse(BaseModel):
    meeting: dict
    outputs: list[dict]
    messages: list[dict] = Field(default_factory=list)
    structured_decision: dict = Field(default_factory=dict)
    files: list[dict] = Field(default_factory=list)
    telegram: dict | None = None
    report: dict


class TradeReviewCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    strategy_signal: str = Field(min_length=1, max_length=80)
    side: str = Field(default="review_only", max_length=32)
    raw_side: str | None = Field(default=None, max_length=64)
    price: float | None = Field(default=None, ge=0)
    volume: int | None = Field(default=None, ge=0)
    timeframe: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)
    technical_indicators: dict = Field(default_factory=dict)
    news_headlines: list[str] = Field(default_factory=list)
    risk_context: dict = Field(default_factory=dict)
    auto_research_metadata: dict = Field(default_factory=dict)
    adapter_warnings: list[str] = Field(default_factory=list)
    input_payload_json: dict = Field(default_factory=dict)


class TickerReviewCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    review_mode: Literal[
        "penny_stock_risk",
        "momentum_review",
        "long_term_review",
        "news_catalyst_review",
        "general_review",
    ] = "penny_stock_risk"
    timeframe: str = Field(default="1d", max_length=32)
    notes: str | None = Field(default=None, max_length=2000)


class AutonomousReviewCreate(BaseModel):
    universe: Literal[
        "mock_penny_stocks",
        "mock_momentum_stocks",
        "mock_watchlist",
        "custom_stub",
    ] = "mock_penny_stocks"
    review_mode: Literal[
        "penny_stock_risk",
        "momentum_review",
        "news_catalyst_review",
        "general_review",
    ] = "penny_stock_risk"
    max_candidates: int = Field(default=5, ge=1, le=20)
    timeframe: str = Field(default="1d", max_length=32)
    notes: str | None = Field(default=None, max_length=2000)


WatchlistReviewMode = Literal[
    "penny_stock_risk",
    "momentum_review",
    "long_term_review",
    "news_catalyst_review",
    "general_review",
]


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    tickers: list[str] = Field(min_length=1, max_length=50)
    review_mode: WatchlistReviewMode = "penny_stock_risk"


class WatchlistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    tickers: list[str] | None = Field(default=None, min_length=1, max_length=50)
    review_mode: WatchlistReviewMode | None = None


ScheduleCadence = Literal[
    "manual_only",
    "daily",
    "weekdays",
    "hourly_stub",
    "market_open_stub",
    "market_close_stub",
]


class WatchlistScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    cadence: ScheduleCadence = "manual_only"
    run_time: str | None = Field(default=None, max_length=5)
    timezone: str = Field(default="Asia/Seoul", max_length=80)
    auto_send_telegram: bool = False


class WatchlistScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    cadence: ScheduleCadence | None = None
    run_time: str | None = Field(default=None, max_length=5)
    timezone: str | None = Field(default=None, max_length=80)
    auto_send_telegram: bool | None = None
