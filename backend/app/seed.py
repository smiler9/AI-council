from __future__ import annotations

from pathlib import Path

from .database import get_connection
from .repository import now_iso


DEFAULT_AGENTS = [
    {
        "agent_key": "financial_statement",
        "name": "Financial Statement Agent",
        "role": "Reviews financial statement quality and capital structure.",
        "focus": "Revenue durability, dilution risk, cash runway, balance sheet pressure.",
    },
    {
        "agent_key": "news_catalyst",
        "name": "News Catalyst Agent",
        "role": "Evaluates company-specific and sector catalysts.",
        "focus": "Press releases, filings, partnerships, regulatory events, event timing.",
    },
    {
        "agent_key": "technical_momentum",
        "name": "Technical Momentum Agent",
        "role": "Reviews price action patterns using mock momentum signals.",
        "focus": "Trend quality, volume behavior, support/resistance, exhaustion risk.",
    },
    {
        "agent_key": "risk_manager",
        "name": "Risk Manager Agent",
        "role": "Frames downside, uncertainty, and position risk.",
        "focus": "Max loss assumptions, liquidity, volatility, concentration, stop discipline.",
    },
    {
        "agent_key": "pump_dump_risk",
        "name": "Pump & Dump Risk Agent",
        "role": "Screens for manipulation-style risk signals.",
        "focus": "Promotion language, thin liquidity, sudden volume, financing overhang.",
    },
    {
        "agent_key": "skeptic",
        "name": "Skeptic Agent",
        "role": "Challenges weak assumptions and overconfident conclusions.",
        "focus": "Evidence gaps, confirmation bias, missing base rates, adverse interpretations.",
    },
    {
        "agent_key": "chairman",
        "name": "Chairman Agent",
        "role": "Synthesizes the meeting into a final decision memo.",
        "focus": "Consensus, dissent, risk posture, next review steps.",
    },
]


def seed_agents(db_path: str | Path | None = None) -> None:
    created_at = now_iso()
    with get_connection(db_path) as connection:
        for agent in DEFAULT_AGENTS:
            connection.execute(
                """
                INSERT INTO agents (agent_key, name, role, focus, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(agent_key) DO UPDATE SET
                    name = excluded.name,
                    role = excluded.role,
                    focus = excluded.focus
                """,
                (
                    agent["agent_key"],
                    agent["name"],
                    agent["role"],
                    agent["focus"],
                    created_at,
                ),
            )

