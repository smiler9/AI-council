from __future__ import annotations

from dataclasses import dataclass

from .llm.providers import AgentLLMRequest, LLMProvider, LLMProviderError, MockLLMProvider


@dataclass(frozen=True)
class CouncilRun:
    outputs: list[dict]
    trade_review: dict
    status: str = "completed"


AGENT_RUN_ORDER = [
    ("financial_statement", "analysis"),
    ("news_catalyst", "analysis"),
    ("technical_momentum", "analysis"),
    ("risk_manager", "analysis"),
    ("pump_dump_risk", "analysis"),
    ("skeptic", "rebuttal"),
    ("chairman", "summary"),
]


def _subject(meeting: dict) -> str:
    if meeting.get("ticker"):
        return f"{meeting['ticker']} / {meeting['topic']}"
    return meeting["topic"]


def _agent_by_key(agents: list[dict]) -> dict[str, dict]:
    return {agent["agent_key"]: agent for agent in agents}


def run_council(meeting: dict, agents: list[dict], provider: LLMProvider) -> CouncilRun:
    by_key = _agent_by_key(agents)
    outputs = []
    for agent_key, stage in AGENT_RUN_ORDER:
        agent = by_key[agent_key]
        response = provider.generate_agent_response(
            AgentLLMRequest(
                meeting=meeting,
                agent=agent,
                stage=stage,
                previous_outputs=outputs,
            )
        )
        outputs.append(
            {
                "agent_key": agent["agent_key"],
                "agent_name": agent["name"],
                "stage": stage,
                "stance": response.stance,
                "confidence": response.confidence,
                "content": response.content,
                "provider_name": provider.name,
                "structured_response": response.as_structured_response(
                    provider_name=provider.name,
                    model=provider.model,
                ),
            }
        )

    return CouncilRun(
        outputs=outputs,
        trade_review=_trade_review(meeting, provider.name),
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
    return CouncilRun(
        outputs=[
            {
                "agent_key": chairman["agent_key"],
                "agent_name": chairman["name"],
                "stage": "summary",
                "stance": "provider_error",
                "confidence": 0.0,
                "content": message,
                "provider_name": provider_name,
                "structured_response": structured_error,
            }
        ],
        trade_review={
            "phase": "phase_2_provider_abstraction",
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
        },
        status="failed",
    )


def _trade_review(meeting: dict, provider_name: str) -> dict:
    subject = _subject(meeting)
    context_files = meeting.get("context_files", [])
    return {
        "phase": "phase_2_provider_abstraction",
        "subject": subject,
        "mock_only": provider_name == "mock",
        "order_execution_allowed": False,
        "recommended_action": "research_only",
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
        "evidence_requirements": [
            "validated financial filings",
            "validated news or SEC catalyst source",
            "live price and volume data",
            "liquidity and spread checks",
            "explicit human or future Risk Gate approval",
        ],
    }
