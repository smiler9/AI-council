from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import LLMConfig
from .prompts import build_user_prompt, system_prompt_for


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider cannot produce a structured response."""


@dataclass(frozen=True)
class AgentLLMRequest:
    meeting: dict
    agent: dict
    stage: str
    previous_outputs: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class AgentLLMResponse:
    stance: str
    confidence: float
    content: str
    risk_flags: list[str] = field(default_factory=list)
    evidence_gaps: list[str] = field(default_factory=list)
    recommended_action: str = "research_only"
    raw: dict[str, Any] = field(default_factory=dict)

    def as_structured_response(self, provider_name: str, model: str | None = None) -> dict:
        return {
            "provider": provider_name,
            "model": model,
            "stance": self.stance,
            "confidence": self.confidence,
            "content": self.content,
            "risk_flags": self.risk_flags,
            "evidence_gaps": self.evidence_gaps,
            "recommended_action": self.recommended_action,
            "raw": self.raw,
        }


class LLMProvider(ABC):
    name: str
    model: str | None = None

    @abstractmethod
    def generate_agent_response(self, request: AgentLLMRequest) -> AgentLLMResponse:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    name = "mock"
    model = "mock-council-v1"

    def generate_agent_response(self, request: AgentLLMRequest) -> AgentLLMResponse:
        subject = _subject(request.meeting)
        templates = {
            "financial_statement": {
                "stance": "cautious",
                "confidence": 0.62,
                "content": (
                    f"Mock review for {subject}: financial quality cannot be confirmed in Phase 1 because no "
                    "filings or live fundamentals are connected. Treat balance-sheet strength, dilution risk, "
                    "and cash runway as open questions before any future trading workflow."
                ),
                "risk_flags": ["unverified_filings", "possible_dilution", "unknown_cash_runway"],
                "evidence_gaps": ["financial statements", "cash runway", "share count history"],
            },
            "news_catalyst": {
                "stance": "neutral",
                "confidence": 0.58,
                "content": (
                    f"Mock catalyst scan for {subject}: no real news feeds are used. A future review should "
                    "separate durable catalysts such as filings or regulatory events from short-lived promotion."
                ),
                "risk_flags": ["unverified_catalyst", "promotion_risk"],
                "evidence_gaps": ["validated news source", "SEC filing source", "event timing"],
            },
            "technical_momentum": {
                "stance": "watchlist",
                "confidence": 0.6,
                "content": (
                    f"Mock momentum read for {subject}: the setup is considered watchlist-only until real price, "
                    "volume, liquidity, and spread data are available. Sudden volume without confirmation should "
                    "not be treated as a buy signal."
                ),
                "risk_flags": ["unknown_liquidity", "unverified_volume", "spread_risk"],
                "evidence_gaps": ["live price data", "volume history", "bid ask spread"],
            },
            "risk_manager": {
                "stance": "defensive",
                "confidence": 0.74,
                "content": (
                    f"Risk frame for {subject}: Phase 1 allows analysis only. No position sizing, stop logic, "
                    "broker routing, or order placement is approved. A future Risk Gate must evaluate liquidity, "
                    "loss limits, and concentration before automation is considered."
                ),
                "risk_flags": ["automation_not_approved", "risk_gate_missing", "loss_limit_undefined"],
                "evidence_gaps": ["risk gate rules", "liquidity checks", "loss limits"],
            },
            "pump_dump_risk": {
                "stance": "high_alert",
                "confidence": 0.71,
                "content": (
                    f"Pump-and-dump screen for {subject}: penny-stock style reviews should assume elevated "
                    "manipulation risk until proven otherwise. Watch for promotional language, thin float, "
                    "toxic financing, and abrupt social-volume spikes."
                ),
                "risk_flags": ["manipulation_risk", "thin_liquidity_risk", "promotion_risk"],
                "evidence_gaps": ["float data", "promotion scan", "financing terms"],
            },
            "skeptic": {
                "stance": "challenge",
                "confidence": 0.79,
                "content": (
                    "The council has not inspected real filings, real news, or live market microstructure. "
                    "Any bullish interpretation would be premature. The strongest conclusion is that the topic "
                    "needs evidence collection, not execution."
                ),
                "risk_flags": ["evidence_gap", "confirmation_bias_risk"],
                "evidence_gaps": ["real filings", "real news", "market microstructure"],
            },
            "chairman": {
                "stance": "research_only",
                "confidence": 0.83,
                "content": (
                    f"Final mock conclusion for {subject}: keep this as research-only. The agents agree that "
                    "risk controls and evidence quality matter more than speed. No automated trade action is "
                    "permitted in Phase 1; the next useful step is attaching validated data sources and a separate "
                    "Risk Gate for future trade-review requests."
                ),
                "risk_flags": ["execution_not_allowed", "risk_gate_required"],
                "evidence_gaps": ["validated data sources", "separate risk gate"],
            },
        }
        template = templates[request.agent["agent_key"]]
        return AgentLLMResponse(
            stance=template["stance"],
            confidence=template["confidence"],
            content=template["content"],
            risk_flags=template["risk_flags"],
            evidence_gaps=template["evidence_gaps"],
            recommended_action="research_only",
            raw={
                "provider_mode": "deterministic_mock",
                "agent_key": request.agent["agent_key"],
                "stage": request.stage,
            },
        )


class LocalOpenAICompatibleProvider(LLMProvider):
    name = "local_openai_compatible"

    def __init__(self, config: LLMConfig):
        self.config = config
        self.model = config.model

    def generate_agent_response(self, request: AgentLLMRequest) -> AgentLLMResponse:
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt_for(request.agent["agent_key"])},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        request.meeting,
                        request.agent,
                        request.stage,
                        request.previous_outputs,
                    ),
                },
            ],
            "temperature": 0.2,
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"local_openai_compatible request failed: {exc}") from exc

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMProviderError("local_openai_compatible returned an invalid chat response") from exc

        parsed = _parse_json_content(content)
        return _structured_response_from_dict(parsed, raw={"provider_response": data})


class StubLLMProvider(LLMProvider):
    def __init__(self, name: str, model: str | None = None):
        self.name = name
        self.model = model

    def generate_agent_response(self, request: AgentLLMRequest) -> AgentLLMResponse:
        raise LLMProviderError(f"{self.name} is a future extension stub and is not implemented")


def get_llm_provider(config: LLMConfig | None = None) -> LLMProvider:
    resolved = config or LLMConfig()
    if resolved.provider == "mock":
        return MockLLMProvider()
    if resolved.provider == "local_openai_compatible":
        return LocalOpenAICompatibleProvider(resolved)
    if resolved.provider in {"openai_stub", "anthropic_stub", "gemini_stub"}:
        return StubLLMProvider(resolved.provider, resolved.model)
    raise LLMProviderError(f"Unsupported LLM provider: {resolved.provider}")


def _subject(meeting: dict) -> str:
    if meeting.get("ticker"):
        return f"{meeting['ticker']} / {meeting['topic']}"
    return meeting["topic"]


def _parse_json_content(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        parsed = json.loads(cleaned.strip())
    except json.JSONDecodeError as exc:
        raise LLMProviderError("LLM response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMProviderError("LLM response JSON must be an object")
    return parsed


def _structured_response_from_dict(data: dict, raw: dict | None = None) -> AgentLLMResponse:
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError) as exc:
        raise LLMProviderError("LLM response confidence must be numeric") from exc
    if not 0.0 <= confidence <= 1.0:
        raise LLMProviderError("LLM response confidence must be between 0.0 and 1.0")

    stance = str(data.get("stance", "")).strip()
    content = str(data.get("content", "")).strip()
    if not stance or not content:
        raise LLMProviderError("LLM response must include non-empty stance and content")

    return AgentLLMResponse(
        stance=stance,
        confidence=confidence,
        content=content,
        risk_flags=_string_list(data.get("risk_flags", [])),
        evidence_gaps=_string_list(data.get("evidence_gaps", [])),
        recommended_action=str(data.get("recommended_action", "research_only")).strip()
        or "research_only",
        raw=raw or data,
    )


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]

