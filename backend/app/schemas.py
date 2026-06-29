from __future__ import annotations

from pydantic import BaseModel, Field


class MeetingCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=240)
    ticker: str | None = Field(default=None, max_length=16)


class MeetingRunResponse(BaseModel):
    meeting: dict
    outputs: list[dict]
    files: list[dict] = Field(default_factory=list)
    report: dict
