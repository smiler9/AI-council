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
        mode = request.meeting.get("mode", "quick_review")
        round_name = request.stage
        context_files = request.meeting.get("context_files", [])
        context_note = _context_note(context_files)
        trade_signal_note = _trade_signal_note(request.meeting.get("trade_signal") or {})
        context_risk_flags = ["attached_context_reviewed"] if context_files else []
        context_evidence_gaps = [
            "uploaded context requires human validation"
        ] if context_files else []
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
        content = template["content"]
        round_note = _round_note(mode, request.agent["agent_key"], round_name)
        if round_note:
            content = f"{content} {round_note}"
        if context_note:
            content = f"{content} Context-aware note: {context_note}"
        if trade_signal_note:
            content = f"{content} Trade signal review note: {trade_signal_note}"
        risk_flags = template["risk_flags"] + context_risk_flags
        evidence_gaps = template["evidence_gaps"] + context_evidence_gaps
        trade_signal_flags, trade_signal_gaps = _trade_signal_provider_flags(
            request.meeting.get("trade_signal") or {}
        )
        risk_flags = risk_flags + trade_signal_flags
        evidence_gaps = evidence_gaps + trade_signal_gaps
        if mode == "risk_gate_review" and request.agent["agent_key"] in {
            "risk_manager",
            "pump_dump_risk",
            "skeptic",
        }:
            risk_flags = risk_flags + ["risk_gate_blocker", "automation_block_required"]
        if mode == "action_plan":
            evidence_gaps = evidence_gaps + ["implementation_tasks_need_validation"]
        return AgentLLMResponse(
            stance=template["stance"],
            confidence=_mode_confidence(template["confidence"], mode, request.agent["agent_key"]),
            content=content,
            risk_flags=risk_flags,
            evidence_gaps=evidence_gaps,
            recommended_action="research_only",
            raw={
                "provider_mode": "deterministic_mock",
                "meeting_mode": mode,
                "agent_key": request.agent["agent_key"],
                "stage": round_name,
                "round": round_name,
                "context_file_count": len(context_files),
                "context_filenames": [
                    file["original_filename"] for file in context_files
                ],
                "trade_signal_review": bool(request.meeting.get("trade_signal")),
            },
        )


class LocalOpenAICompatibleProvider(LLMProvider):
    name = "local_openai_compatible"

    def __init__(self, config: LLMConfig):
        self.config = config
        self.model = config.model

    def list_models(self) -> list[str]:
        url = f"{self.config.base_url.rstrip('/')}/models"
        headers = {"Accept": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise LLMProviderError(f"local_openai_compatible models request failed: {exc}") from exc
        return _model_ids_from_response(data)

    def connection_status(self) -> dict:
        try:
            models = self.list_models()
        except LLMProviderError as exc:
            return {
                "provider": self.name,
                "base_url": self.config.base_url,
                "available": False,
                "model": self.model,
                "models": [],
                "selected_model_available": False,
                "error": str(exc),
            }
        return {
            "provider": self.name,
            "base_url": self.config.base_url,
            "available": True,
            "model": self.model,
            "models": models,
            "selected_model_available": self.model in models if models else False,
            "error": None,
        }

    def generate_agent_response(self, request: AgentLLMRequest) -> AgentLLMResponse:
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "/no_think\n"
                        f"{system_prompt_for(request.agent['agent_key'])} "
                        "Return only the final JSON object in message.content."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "/no_think\n"
                        + build_user_prompt(
                            request.meeting,
                            request.agent,
                            request.stage,
                            request.previous_outputs,
                        )
                    ),
                },
            ],
            "temperature": 0.2,
            "stream": False,
            "max_tokens": self.config.max_tokens,
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
        return _structured_response_from_dict(parsed, raw=_safe_chat_response_metadata(data))


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


def _context_note(context_files: list[dict]) -> str:
    ready_files = [file for file in context_files if file.get("status") == "ready"]
    if not context_files:
        return ""
    filenames = ", ".join(file["original_filename"] for file in context_files[:5])
    summaries = " ".join(file["summary"] for file in ready_files[:3])
    if not summaries:
        summaries = "No ready text context was available; unsupported files were not used as evidence."
    return (
        f"Referenced {len(context_files)} attached file(s): {filenames}. "
        f"Key context summary: {summaries[:900]} "
        "Treat uploaded material as user-provided evidence that still requires validation."
    )


def _trade_signal_note(trade_signal: dict) -> str:
    if not trade_signal:
        return ""
    risk_context = trade_signal.get("risk_context") or {}
    spread_pct = risk_context.get("spread_pct", "unknown")
    premarket = bool(risk_context.get("premarket"))
    headline_count = len(trade_signal.get("news_headlines") or [])
    return (
        f"Reviewed external signal {trade_signal.get('strategy_signal', 'unknown')} for "
        f"{trade_signal.get('ticker', 'unknown')} on timeframe "
        f"{trade_signal.get('timeframe') or 'unspecified'}. Side "
        f"'{trade_signal.get('side', 'review_only')}' is treated only as review context. "
        f"Spread pct: {spread_pct}; volume: {trade_signal.get('volume', 'unknown')}; "
        f"premarket: {premarket}; news headline count: {headline_count}. "
        "No order creation, routing, or broker action is allowed."
    )


def _trade_signal_provider_flags(trade_signal: dict) -> tuple[list[str], list[str]]:
    if not trade_signal:
        return [], []
    flags = ["external_trade_signal_review"]
    gaps = []
    risk_context = trade_signal.get("risk_context") or {}
    spread_pct = _as_float(risk_context.get("spread_pct"))
    volume = _as_float(trade_signal.get("volume"))
    if spread_pct is None:
        gaps.append("spread data")
    elif spread_pct >= 5:
        flags.append("very_high_spread_risk")
    elif spread_pct >= 3:
        flags.append("high_spread_risk")
    if volume is None or volume <= 0:
        gaps.append("validated volume")
    elif volume < 1_000_000:
        flags.append("low_volume_risk")
    if bool(risk_context.get("premarket")):
        flags.append("premarket_session_risk")
    if not trade_signal.get("news_headlines"):
        flags.append("missing_news_context")
        gaps.append("news catalyst validation")
    return flags, gaps


def _round_note(mode: str, agent_key: str, round_name: str) -> str:
    if round_name == "initial_opinion":
        return f"Round 1 initial opinion for {mode}: establish the agent's first-pass evidence view."
    if round_name == "rebuttal":
        return "Round 2 rebuttal: challenge unsupported assumptions and identify downside scenarios."
    if round_name == "revision":
        return "Round 3 revision: adjust the original view after skeptic and risk-manager objections."
    if round_name == "chairman_summary":
        if mode == "action_plan":
            return "Round 4 chairman summary: convert the review into follow-up tasks without enabling execution."
        return "Round 4 chairman summary: synthesize consensus, dissent, risk posture, and next review steps."
    if mode == "risk_gate_review" and agent_key in {"risk_manager", "pump_dump_risk", "skeptic"}:
        return "Risk gate mode: treat unresolved liquidity, manipulation, or automation concerns as blockers."
    if mode == "deep_debate":
        return "Deep debate mode: explicitly compare supporting and opposing interpretations."
    if mode == "skeptic_review":
        return "Skeptic review mode: emphasize base-rate risk and missing evidence."
    return ""


def _mode_confidence(base_confidence: float, mode: str, agent_key: str) -> float:
    if mode == "risk_gate_review" and agent_key in {"risk_manager", "pump_dump_risk", "skeptic"}:
        return min(0.9, round(base_confidence + 0.08, 2))
    if mode == "deep_debate":
        return min(0.86, round(base_confidence + 0.03, 2))
    if mode == "skeptic_review" and agent_key == "skeptic":
        return min(0.9, round(base_confidence + 0.09, 2))
    return base_confidence


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_json_content(content: str) -> dict:
    cleaned = _strip_response_wrappers(content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = _extract_response_object(cleaned)
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


def _safe_chat_response_metadata(data: dict) -> dict:
    choices = data.get("choices", []) if isinstance(data, dict) else []
    first_choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = first_choice.get("message", {}) if isinstance(first_choice, dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    return {
        "provider_response": {
            "id": data.get("id"),
            "model": data.get("model"),
            "object": data.get("object"),
            "finish_reason": first_choice.get("finish_reason"),
            "usage": data.get("usage", {}),
            "content_length": len(content or ""),
            "has_reasoning": bool(
                isinstance(message, dict)
                and (message.get("reasoning") or message.get("reasoning_content"))
            ),
        }
    }


def _strip_response_wrappers(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("<think>"):
        end = cleaned.find("</think>")
        if end != -1:
            cleaned = cleaned[end + len("</think>") :].strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _extract_response_object(content: str) -> dict:
    decoder = json.JSONDecoder()
    candidates = []
    for index, character in enumerate(content):
        if character != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            candidates.append(parsed)
    if not candidates:
        raise LLMProviderError("LLM response was not valid JSON")
    for candidate in candidates:
        if {"stance", "confidence", "content"}.issubset(candidate):
            return candidate
    return candidates[-1]


def _model_ids_from_response(data: dict) -> list[str]:
    if not isinstance(data, dict):
        raise LLMProviderError("local_openai_compatible models response must be an object")

    raw_models = data.get("data")
    if raw_models is None:
        raw_models = data.get("models")
    if not isinstance(raw_models, list):
        raise LLMProviderError("local_openai_compatible models response did not include a model list")

    models = []
    for item in raw_models:
        if isinstance(item, str):
            model_id = item
        elif isinstance(item, dict):
            model_id = item.get("id") or item.get("name") or item.get("model")
        else:
            model_id = None
        if model_id:
            models.append(str(model_id))
    return models
