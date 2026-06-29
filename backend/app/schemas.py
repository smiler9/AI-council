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
