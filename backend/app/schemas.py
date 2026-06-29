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
    price: float | None = Field(default=None, ge=0)
    volume: int | None = Field(default=None, ge=0)
    timeframe: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)
    technical_indicators: dict = Field(default_factory=dict)
    news_headlines: list[str] = Field(default_factory=list)
    risk_context: dict = Field(default_factory=dict)
