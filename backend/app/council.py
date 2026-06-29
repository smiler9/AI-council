from __future__ import annotations

from dataclasses import dataclass


PRIMARY_AGENT_KEYS = [
    "financial_statement",
    "news_catalyst",
    "technical_momentum",
    "risk_manager",
    "pump_dump_risk",
]


@dataclass(frozen=True)
class CouncilRun:
    outputs: list[dict]
    trade_review: dict


def _subject(meeting: dict) -> str:
    if meeting.get("ticker"):
        return f"{meeting['ticker']} / {meeting['topic']}"
    return meeting["topic"]


def _agent_by_key(agents: list[dict]) -> dict[str, dict]:
    return {agent["agent_key"]: agent for agent in agents}


def run_mock_council(meeting: dict, agents: list[dict]) -> CouncilRun:
    by_key = _agent_by_key(agents)
    subject = _subject(meeting)

    primary_templates = {
        "financial_statement": {
            "stance": "cautious",
            "confidence": 0.62,
            "content": (
                f"Mock review for {subject}: financial quality cannot be confirmed in Phase 1 because no "
                "filings or live fundamentals are connected. Treat balance-sheet strength, dilution risk, "
                "and cash runway as open questions before any future trading workflow."
            ),
        },
        "news_catalyst": {
            "stance": "neutral",
            "confidence": 0.58,
            "content": (
                f"Mock catalyst scan for {subject}: no real news feeds are used. A future review should "
                "separate durable catalysts such as filings or regulatory events from short-lived promotion."
            ),
        },
        "technical_momentum": {
            "stance": "watchlist",
            "confidence": 0.6,
            "content": (
                f"Mock momentum read for {subject}: the setup is considered watchlist-only until real price, "
                "volume, liquidity, and spread data are available. Sudden volume without confirmation should "
                "not be treated as a buy signal."
            ),
        },
        "risk_manager": {
            "stance": "defensive",
            "confidence": 0.74,
            "content": (
                f"Risk frame for {subject}: Phase 1 allows analysis only. No position sizing, stop logic, "
                "broker routing, or order placement is approved. A future Risk Gate must evaluate liquidity, "
                "loss limits, and concentration before automation is considered."
            ),
        },
        "pump_dump_risk": {
            "stance": "high_alert",
            "confidence": 0.71,
            "content": (
                f"Pump-and-dump screen for {subject}: penny-stock style reviews should assume elevated "
                "manipulation risk until proven otherwise. Watch for promotional language, thin float, "
                "toxic financing, and abrupt social-volume spikes."
            ),
        },
    }

    outputs = []
    for agent_key in PRIMARY_AGENT_KEYS:
        agent = by_key[agent_key]
        template = primary_templates[agent_key]
        outputs.append(
            {
                "agent_key": agent["agent_key"],
                "agent_name": agent["name"],
                "stage": "analysis",
                "stance": template["stance"],
                "confidence": template["confidence"],
                "content": template["content"],
            }
        )

    skeptic = by_key["skeptic"]
    outputs.append(
        {
            "agent_key": skeptic["agent_key"],
            "agent_name": skeptic["name"],
            "stage": "rebuttal",
            "stance": "challenge",
            "confidence": 0.79,
            "content": (
                "The council has not inspected real filings, real news, or live market microstructure. "
                "Any bullish interpretation would be premature. The strongest conclusion is that the topic "
                "needs evidence collection, not execution."
            ),
        }
    )

    chairman = by_key["chairman"]
    outputs.append(
        {
            "agent_key": chairman["agent_key"],
            "agent_name": chairman["name"],
            "stage": "summary",
            "stance": "research_only",
            "confidence": 0.83,
            "content": (
                f"Final mock conclusion for {subject}: keep this as research-only. The agents agree that "
                "risk controls and evidence quality matter more than speed. No automated trade action is "
                "permitted in Phase 1; the next useful step is attaching validated data sources and a separate "
                "Risk Gate for future trade-review requests."
            ),
        }
    )

    trade_review = {
        "phase": "phase_1_mock",
        "subject": subject,
        "mock_only": True,
        "order_execution_allowed": False,
        "recommended_action": "research_only",
        "requires_future_risk_gate": True,
        "risk_gate_status": "not_implemented",
        "broker_integration_status": "not_connected",
        "evidence_requirements": [
            "validated financial filings",
            "validated news or SEC catalyst source",
            "live price and volume data",
            "liquidity and spread checks",
            "explicit human or future Risk Gate approval",
        ],
    }
    return CouncilRun(outputs=outputs, trade_review=trade_review)

