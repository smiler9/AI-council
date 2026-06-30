from __future__ import annotations

from dataclasses import dataclass

from .llm.providers import AgentLLMRequest, LLMProvider, LLMProviderError, MockLLMProvider


MEETING_MODES = {
    "quick_review",
    "deep_debate",
    "skeptic_review",
    "risk_gate_review",
    "action_plan",
}

SAFETY_BOUNDARY = (
    "AI Council does not execute trades or connect to broker APIs. "
    "This output is for review, risk analysis, and decision support only."
)
KOREAN_SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)

INITIAL_AGENT_KEYS = [
    "financial_statement",
    "news_catalyst",
    "technical_momentum",
    "risk_manager",
    "pump_dump_risk",
]
REBUTTAL_AGENT_KEYS = ["skeptic", "risk_manager"]
REVISION_AGENT_KEYS = [
    "financial_statement",
    "news_catalyst",
    "technical_momentum",
    "risk_manager",
    "pump_dump_risk",
]


@dataclass(frozen=True)
class CouncilRun:
    outputs: list[dict]
    messages: list[dict]
    trade_review: dict
    structured_decision: dict
    status: str = "completed"


def _subject(meeting: dict) -> str:
    if meeting.get("ticker"):
        return f"{meeting['ticker']} / {meeting['topic']}"
    return meeting["topic"]


def _agent_by_key(agents: list[dict]) -> dict[str, dict]:
    return {agent["agent_key"]: agent for agent in agents}


def run_council(meeting: dict, agents: list[dict], provider: LLMProvider) -> CouncilRun:
    by_key = _agent_by_key(agents)
    messages: list[dict] = []

    for agent_key in INITIAL_AGENT_KEYS:
        messages.append(
            _run_agent_round(
                meeting=meeting,
                agent=by_key[agent_key],
                round_name="initial_opinion",
                message_type="analysis",
                provider=provider,
                previous_messages=messages,
            )
        )

    for agent_key in REBUTTAL_AGENT_KEYS:
        messages.append(
            _run_agent_round(
                meeting=meeting,
                agent=by_key[agent_key],
                round_name="rebuttal",
                message_type="rebuttal",
                provider=provider,
                previous_messages=messages,
            )
        )

    for agent_key in REVISION_AGENT_KEYS:
        messages.append(
            _run_agent_round(
                meeting=meeting,
                agent=by_key[agent_key],
                round_name="revision",
                message_type="revision",
                provider=provider,
                previous_messages=messages,
            )
        )

    messages.append(
        _run_agent_round(
            meeting=meeting,
            agent=by_key["chairman"],
            round_name="chairman_summary",
            message_type="summary",
            provider=provider,
            previous_messages=messages,
        )
    )

    structured_decision = build_structured_decision(meeting, messages, provider.name)
    messages.append(_structured_decision_message(meeting, by_key["chairman"], structured_decision, provider))
    outputs = _legacy_outputs(messages)

    return CouncilRun(
        outputs=outputs,
        messages=messages,
        trade_review=_trade_review(meeting, provider.name, structured_decision),
        structured_decision=structured_decision,
        status="completed",
    )


def run_mock_council(meeting: dict, agents: list[dict]) -> CouncilRun:
    return run_council(meeting, agents, MockLLMProvider())


def build_failed_council_run(
    meeting: dict,
    agents: list[dict],
    provider_name: str,
    error: LLMProviderError,
) -> CouncilRun:
    by_key = _agent_by_key(agents)
    subject = _subject(meeting)
    context_files = meeting.get("context_files", [])
    chairman = by_key.get("chairman") or agents[-1]
    message = (
        f"LLM provider '{provider_name}' failed while reviewing {subject}. "
        "The meeting was stopped safely. No broker connection, order routing, or trade execution was attempted."
    )
    structured_error = {
        "provider": provider_name,
        "model": None,
        "stance": "provider_error",
        "confidence": 0.0,
        "content": message,
        "risk_flags": ["provider_failure", "review_incomplete"],
        "evidence_gaps": ["provider response unavailable"],
        "recommended_action": "needs_more_evidence",
        "error": str(error),
    }
    structured_decision = {
        "decision": "NEED_MORE_DATA",
        "confidence": 0.0,
        "risk_level": "critical",
        "trade_allowed": False,
        "position_size_multiplier": 0.0,
        "primary_reasons": ["Provider failed before the council could complete review."],
        "risk_flags": ["provider_failure", "review_incomplete"],
        "required_follow_up": ["Restore provider availability and rerun the meeting."],
        "data_quality": "failed",
        "order_execution_allowed": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }
    failed_output = {
        "agent_id": chairman.get("id"),
        "agent_key": chairman["agent_key"],
        "agent_name": chairman["name"],
        "round": "chairman_summary",
        "stage": "summary",
        "message_type": "summary",
        "stance": "provider_error",
        "confidence": 0.0,
        "risk_level": "critical",
        "content": message,
        "provider_name": provider_name,
        "structured_response": structured_error,
    }
    return CouncilRun(
        outputs=[failed_output],
        messages=[failed_output],
        trade_review={
            "phase": "phase_4_debate_engine",
            "subject": subject,
            "mock_only": provider_name == "mock",
            "order_execution_allowed": False,
            "recommended_action": "needs_more_evidence",
            "review_status": "failed",
            "provider": provider_name,
            "provider_error": str(error),
            "requires_future_risk_gate": True,
            "risk_gate_status": "not_implemented",
            "broker_integration_status": "not_connected",
            "context_file_count": len(context_files),
            "structured_decision": structured_decision,
            "safety_boundary": SAFETY_BOUNDARY,
        },
        structured_decision=structured_decision,
        status="failed",
    )


def build_structured_decision(meeting: dict, messages: list[dict], provider_name: str) -> dict:
    mode = meeting.get("mode", "quick_review")
    context_files = meeting.get("context_files", [])
    trade_signal = meeting.get("trade_signal") or {}
    risk_flags = _collect_unique_flags(messages, "risk_flags")
    evidence_gaps = _collect_unique_flags(messages, "evidence_gaps")
    trade_signal_rules = _trade_signal_rules(trade_signal)
    risk_flags = _merge_unique(risk_flags, trade_signal_rules["risk_flags"])
    evidence_gaps = _merge_unique(evidence_gaps, trade_signal_rules["evidence_gaps"])
    data_quality = (
        "limited"
        if evidence_gaps or not context_files or trade_signal_rules["data_quality"] == "limited"
        else "moderate"
    )
    risk_level = _risk_level_for_mode(mode, context_files, risk_flags, trade_signal)

    if risk_level == "critical":
        decision = "BLOCK"
    elif risk_level == "high":
        decision = "HOLD"
    elif data_quality == "limited":
        decision = "NEED_MORE_DATA"
    else:
        decision = "HOLD"

    primary_reasons = [
        f"Meeting mode '{mode}' completed through structured debate rounds.",
        "Uploaded and live evidence remains review-only and requires validation.",
    ]
    if context_files:
        primary_reasons.append(f"{len(context_files)} attached context file(s) were considered.")
    if trade_signal:
        primary_reasons.append(
            "External trade signal was reviewed as read-only context, not as an executable order."
        )
    if mode == "risk_gate_review":
        primary_reasons.append("Risk gate review prioritizes blocking unsafe automation paths.")
    if mode == "action_plan":
        primary_reasons.append("Action plan mode produced follow-up tasks without enabling execution.")
    primary_reasons.extend(trade_signal_rules["primary_reasons"])

    required_follow_up = [
        "Validate financial filings, news catalysts, and market data before any future review.",
        "Run a separate Risk Gate before any future automation integration.",
    ]
    if evidence_gaps:
        required_follow_up.append("Resolve evidence gaps: " + ", ".join(evidence_gaps[:6]))
    if mode == "action_plan":
        required_follow_up.extend(
            [
                "Draft data-source validation checks.",
                "Prepare a Codex task to implement review-only data adapters.",
            ]
        )
    required_follow_up.extend(trade_signal_rules["required_follow_up"])

    decision_payload = {
        "decision": decision,
        "confidence": _decision_confidence(mode, data_quality),
        "risk_level": risk_level,
        "trade_allowed": False,
        "position_size_multiplier": 0.0,
        "primary_reasons": primary_reasons,
        "risk_flags": risk_flags,
        "required_follow_up": required_follow_up,
        "data_quality": data_quality,
        "order_execution_allowed": False,
        "provider": provider_name,
        "meeting_mode": mode,
        "safety_boundary": SAFETY_BOUNDARY,
    }
    if mode == "action_plan":
        decision_payload["codex_prompt"] = (
            "Implement review-only validation tasks for AI Council. Do not connect broker APIs "
            "or implement order execution."
        )
    return decision_payload


def _run_agent_round(
    meeting: dict,
    agent: dict,
    round_name: str,
    message_type: str,
    provider: LLMProvider,
    previous_messages: list[dict],
) -> dict:
    response = provider.generate_agent_response(
        AgentLLMRequest(
            meeting=meeting,
            agent=agent,
            stage=round_name,
            previous_outputs=previous_messages,
        )
    )
    structured_response = response.as_structured_response(
        provider_name=provider.name,
        model=provider.model,
    )
    risk_level = _message_risk_level(
        meeting.get("mode", "quick_review"),
        agent["agent_key"],
        round_name,
        structured_response.get("risk_flags", []),
    )
    return {
        "agent_id": agent.get("id"),
        "agent_key": agent["agent_key"],
        "agent_name": agent["name"],
        "round": round_name,
        "stage": round_name,
        "message_type": message_type,
        "stance": response.stance,
        "confidence": response.confidence,
        "risk_level": risk_level,
        "content": response.content,
        "provider_name": provider.name,
        "structured_response": structured_response,
    }


def _structured_decision_message(
    meeting: dict,
    chairman: dict,
    structured_decision: dict,
    provider: LLMProvider,
) -> dict:
    content = (
        f"Structured decision: {structured_decision['decision']} with "
        f"{structured_decision['risk_level']} risk. "
        f"Order execution allowed: {structured_decision['order_execution_allowed']}."
    )
    return {
        "agent_id": chairman.get("id"),
        "agent_key": chairman["agent_key"],
        "agent_name": chairman["name"],
        "round": "structured_decision",
        "stage": "structured_decision",
        "message_type": "decision",
        "stance": structured_decision["decision"].lower(),
        "confidence": structured_decision["confidence"],
        "risk_level": structured_decision["risk_level"],
        "content": content,
        "provider_name": provider.name,
        "structured_response": structured_decision,
    }


def _legacy_outputs(messages: list[dict]) -> list[dict]:
    outputs = []
    for agent_key in INITIAL_AGENT_KEYS:
        message = _latest_message(messages, agent_key, preferred_round="revision")
        if message:
            outputs.append({**message, "stage": "analysis"})
    skeptic = _latest_message(messages, "skeptic", preferred_round="rebuttal")
    if skeptic:
        outputs.append({**skeptic, "stage": "rebuttal"})
    chairman = _latest_message(messages, "chairman", preferred_round="chairman_summary")
    if chairman:
        outputs.append({**chairman, "stage": "summary"})
    return outputs


def _latest_message(messages: list[dict], agent_key: str, preferred_round: str) -> dict | None:
    for message in reversed(messages):
        if message["agent_key"] == agent_key and message["round"] == preferred_round:
            return message
    for message in reversed(messages):
        if message["agent_key"] == agent_key:
            return message
    return None


def _trade_review(meeting: dict, provider_name: str, structured_decision: dict) -> dict:
    subject = _subject(meeting)
    context_files = meeting.get("context_files", [])
    trade_signal = meeting.get("trade_signal") or {}
    return {
        "phase": "phase_4_debate_engine",
        "subject": subject,
        "meeting_mode": meeting.get("mode", "quick_review"),
        "external_trade_signal_review": bool(trade_signal),
        "mock_only": provider_name == "mock",
        "order_execution_allowed": False,
        "trade_allowed": structured_decision["trade_allowed"],
        "recommended_action": structured_decision["decision"],
        "review_status": "completed",
        "provider": provider_name,
        "requires_future_risk_gate": True,
        "risk_gate_status": "not_implemented",
        "broker_integration_status": "not_connected",
        "context_file_count": len(context_files),
        "context_files": [
            {
                "id": file["id"],
                "filename": file["original_filename"],
                "status": file["status"],
                "file_type": file["file_type"],
            }
            for file in context_files
        ],
        "trade_signal": trade_signal,
        "structured_decision": structured_decision,
        "safety_boundary": SAFETY_BOUNDARY,
        "evidence_requirements": [
            "validated financial filings",
            "validated news or SEC catalyst source",
            "live price and volume data",
            "liquidity and spread checks",
            "explicit human or future Risk Gate approval",
        ],
    }


def _message_risk_level(
    mode: str,
    agent_key: str,
    round_name: str,
    risk_flags: list[str],
) -> str:
    if mode == "risk_gate_review" and agent_key in {"risk_manager", "pump_dump_risk", "skeptic"}:
        return "critical"
    if "manipulation_risk" in risk_flags or "automation_not_approved" in risk_flags:
        return "high"
    if round_name == "rebuttal" or agent_key in {"risk_manager", "pump_dump_risk", "skeptic"}:
        return "high" if mode in {"deep_debate", "skeptic_review"} else "medium"
    return "medium"


def _risk_level_for_mode(
    mode: str,
    context_files: list[dict],
    risk_flags: list[str],
    trade_signal: dict | None = None,
) -> str:
    if mode == "risk_gate_review" and trade_signal:
        if "very_high_spread_risk" in risk_flags:
            return "critical"
        if {
            "high_spread_risk",
            "low_volume_risk",
            "premarket_session_risk",
            "missing_news_context",
            "manipulation_risk",
            "automation_not_approved",
        }.intersection(risk_flags):
            return "high"
        return "medium"
    if mode == "risk_gate_review":
        return "critical"
    if mode in {"deep_debate", "skeptic_review"}:
        return "high"
    if "manipulation_risk" in risk_flags or "automation_not_approved" in risk_flags:
        return "high"
    if not context_files:
        return "medium"
    return "medium"


def _decision_confidence(mode: str, data_quality: str) -> float:
    if mode == "risk_gate_review":
        return 0.72
    if mode == "deep_debate":
        return 0.66
    if data_quality == "limited":
        return 0.58
    return 0.62


def _collect_unique_flags(messages: list[dict], key: str) -> list[str]:
    values = []
    seen = set()
    for message in messages:
        response = message.get("structured_response", {})
        for value in response.get(key, []):
            if value not in seen:
                seen.add(value)
                values.append(value)
    return values[:12]


def _trade_signal_rules(trade_signal: dict) -> dict:
    rules = {
        "risk_flags": [],
        "evidence_gaps": [],
        "primary_reasons": [],
        "required_follow_up": [],
        "data_quality": "moderate",
    }
    if not trade_signal:
        return rules

    risk_context = trade_signal.get("risk_context") or {}
    spread_pct = _as_float(risk_context.get("spread_pct"))
    volume = _as_float(trade_signal.get("volume"))
    news_headlines = trade_signal.get("news_headlines") or []
    side = str(trade_signal.get("side") or "").strip().lower()

    if spread_pct is None:
        rules["evidence_gaps"].append("spread data")
        rules["data_quality"] = "limited"
    elif spread_pct >= 5:
        rules["risk_flags"].append("very_high_spread_risk")
        rules["primary_reasons"].append(f"Spread is very high at {spread_pct:.2f}%.")
        rules["required_follow_up"].append("Review bid/ask spread and liquidity before any future action.")
    elif spread_pct >= 3:
        rules["risk_flags"].append("high_spread_risk")
        rules["primary_reasons"].append(f"Spread is elevated at {spread_pct:.2f}%.")
        rules["required_follow_up"].append("Confirm spread compression and executable liquidity.")

    if volume is None or volume <= 0:
        rules["evidence_gaps"].append("validated volume")
        rules["data_quality"] = "limited"
    elif volume < 1_000_000:
        rules["risk_flags"].append("low_volume_risk")
        rules["primary_reasons"].append("Volume is below the minimum review threshold for penny-stock liquidity.")
        rules["required_follow_up"].append("Validate volume, float, and dollar liquidity.")

    if bool(risk_context.get("premarket")):
        rules["risk_flags"].append("premarket_session_risk")
        rules["primary_reasons"].append("Signal occurred in premarket conditions.")
        rules["required_follow_up"].append("Recheck spread, liquidity, and catalyst quality during regular hours.")

    if not news_headlines:
        rules["risk_flags"].append("missing_news_context")
        rules["evidence_gaps"].append("news catalyst validation")
        rules["required_follow_up"].append("Attach validated news, SEC filing, or catalyst source.")
        rules["data_quality"] = "limited"

    if side in {"buy", "sell", "short", "order", "market_order", "limit_order"}:
        rules["risk_flags"].append("execution_language_treated_as_review_context")
        rules["primary_reasons"].append(
            f"Input side '{side}' was stored only as review context and was not treated as an order."
        )

    return rules


def _merge_unique(left: list[str], right: list[str]) -> list[str]:
    values = []
    seen = set()
    for value in left + right:
        if value not in seen:
            seen.add(value)
            values.append(value)
    return values[:16]


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
