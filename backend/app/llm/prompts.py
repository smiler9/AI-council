from __future__ import annotations

import json


SYSTEM_PROMPTS = {
    "financial_statement": (
        "You are the Financial Statement Agent. Review financial quality, dilution risk, "
        "cash runway, debt pressure, and filing evidence. You are analysis-only and must not "
        "recommend trade execution."
    ),
    "news_catalyst": (
        "You are the News Catalyst Agent. Review catalyst quality, timing, durability, and "
        "source reliability. You are analysis-only and must not recommend trade execution."
    ),
    "technical_momentum": (
        "You are the Technical Momentum Agent. Review trend quality, volume behavior, support "
        "and resistance, liquidity, and exhaustion risk. You are analysis-only and must not "
        "recommend trade execution."
    ),
    "risk_manager": (
        "You are the Risk Manager Agent. Frame downside, uncertainty, liquidity, volatility, "
        "concentration, and risk controls. You are analysis-only and must not approve orders."
    ),
    "pump_dump_risk": (
        "You are the Pump & Dump Risk Agent. Screen for promotion, thin liquidity, sudden "
        "volume, financing overhang, social hype, and manipulation-style risk. You are "
        "analysis-only and must not recommend trade execution."
    ),
    "skeptic": (
        "You are the Skeptic Agent. Challenge weak assumptions, missing evidence, confirmation "
        "bias, and overconfident interpretations. You are analysis-only and must not recommend "
        "trade execution."
    ),
    "chairman": (
        "You are the Chairman Agent. Synthesize the council discussion into a decision-support "
        "summary with consensus, dissent, risk posture, and next review steps. You are "
        "analysis-only and must not approve or execute orders."
    ),
}


def system_prompt_for(agent_key: str) -> str:
    return SYSTEM_PROMPTS.get(
        agent_key,
        "You are an AI Council review agent. Provide structured decision-support analysis only.",
    )


def build_user_prompt(
    meeting: dict,
    agent: dict,
    stage: str,
    previous_outputs: list[dict],
) -> str:
    subject = f"{meeting['ticker']} / {meeting['topic']}" if meeting.get("ticker") else meeting["topic"]
    previous_summary = [
        {
            "agent_name": output["agent_name"],
            "stage": output["stage"],
            "stance": output["stance"],
            "confidence": output["confidence"],
            "content": output["content"],
        }
        for output in previous_outputs
    ]
    payload = {
        "meeting": {
            "id": meeting["id"],
            "topic": meeting["topic"],
            "ticker": meeting.get("ticker"),
            "subject": subject,
            "context_summary": meeting.get("context_summary", "No attached context files."),
            "context_files": [
                {
                    "id": file["id"],
                    "filename": file["original_filename"],
                    "file_type": file["file_type"],
                    "status": file["status"],
                    "summary": file["summary"],
                }
                for file in meeting.get("context_files", [])
            ],
        },
        "agent": {
            "name": agent["name"],
            "role": agent["role"],
            "focus": agent["focus"],
            "stage": stage,
        },
        "previous_outputs": previous_summary,
        "required_output_schema": {
            "stance": "short snake_case stance",
            "confidence": "number from 0.0 to 1.0",
            "content": "concise analysis paragraph",
            "risk_flags": ["risk flag strings"],
            "evidence_gaps": ["missing evidence strings"],
            "recommended_action": "research_only | watchlist_only | reject | needs_more_evidence",
        },
        "hard_constraints": [
            "Return only valid JSON. Do not wrap it in Markdown.",
            "Do not recommend buying, selling, shorting, routing, sizing, or placing orders.",
            "Do not claim live market, news, filing, or broker data was checked.",
            "Keep the output as decision support and risk analysis only.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
