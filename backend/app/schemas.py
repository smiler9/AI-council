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


class PaperPortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    starting_cash: float = Field(default=10000, gt=0)


class PaperPortfolioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    status: Literal["active", "archived"] | None = None


class PaperSimulationCreate(BaseModel):
    source_type: Literal[
        "trade_review",
        "ticker_review",
        "autonomous_review",
        "watchlist_review",
        "webhook_event",
    ]
    source_id: str = Field(min_length=1, max_length=80)
    simulation_policy: Literal[
        "risk_gate_conservative",
        "observe_only",
        "aggressive_research_only",
    ] = "risk_gate_conservative"
    max_notional_per_trade: float = Field(default=100, gt=0)
    allow_only_decision: bool = False
    slippage_bps: float = Field(default=25, ge=0)
    spread_bps: float = Field(default=50, ge=0)
    max_spread_pct: float = Field(default=5.0, ge=0)
    take_profit_pct: float = Field(default=8.0, gt=0)
    stop_loss_pct: float = Field(default=5.0, gt=0)
    max_holding_minutes: int = Field(default=240, ge=1)
    allow_partial_fill_simulation: bool = False
    simulation_only: bool = True


class PaperExitSimulationCreate(BaseModel):
    exit_reason: Literal[
        "manual_simulated_exit",
        "simulated_take_profit",
        "simulated_stop_loss",
        "simulated_risk_exit",
        "simulated_data_quality_exit",
    ] = "manual_simulated_exit"
    exit_price: float | None = Field(default=None, gt=0)
    slippage_bps: float = Field(default=25, ge=0)
    spread_bps: float = Field(default=50, ge=0)
    simulation_only: bool = True


class PaperExitEvaluationCreate(BaseModel):
    execute_simulated_exits: bool = False
    take_profit_pct: float = Field(default=8.0, gt=0)
    stop_loss_pct: float = Field(default=5.0, gt=0)
    slippage_bps: float = Field(default=25, ge=0)
    spread_bps: float = Field(default=50, ge=0)
    simulation_only: bool = True
