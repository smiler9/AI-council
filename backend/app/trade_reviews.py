from __future__ import annotations

from pathlib import Path
from typing import Any

from .council import build_failed_council_run, run_council
from .llm.config import LLMConfig
from .llm.providers import LLMProviderError, get_llm_provider
from .reports import write_markdown_report
from .repository import (
    create_meeting,
    create_trade_review,
    get_meeting,
    get_meeting_messages,
    get_meeting_outputs,
    list_agents,
    replace_meeting_outputs,
    upsert_report,
)
from .schemas import TradeReviewCreate


def run_trade_review(
    payload: TradeReviewCreate,
    *,
    db_path: str | Path | None,
    report_dir: str | Path | None,
    llm_config: LLMConfig,
) -> dict:
    input_payload = _normalized_payload(payload)
    meeting = create_meeting(
        topic=_meeting_topic(input_payload),
        ticker=input_payload["ticker"],
        db_path=db_path,
        mode="risk_gate_review",
    )
    meeting = get_meeting(meeting["id"], db_path)
    meeting["context_files"] = []
    meeting["context_summary"] = _trade_signal_context_summary(input_payload)
    meeting["trade_signal"] = input_payload

    agents = list_agents(db_path)
    provider = get_llm_provider(llm_config)
    try:
        council_run = run_council(meeting, agents, provider)
    except LLMProviderError as exc:
        council_run = build_failed_council_run(
            meeting=meeting,
            agents=agents,
            provider_name=provider.name,
            error=exc,
        )

    replace_meeting_outputs(
        meeting_id=meeting["id"],
        outputs=council_run.outputs,
        trade_review=council_run.trade_review,
        db_path=db_path,
        status=council_run.status,
        messages=council_run.messages,
        structured_decision=council_run.structured_decision,
    )

    updated_meeting = get_meeting(meeting["id"], db_path)
    updated_meeting["context_files"] = []
    updated_meeting["context_summary"] = _trade_signal_context_summary(input_payload)
    updated_meeting["trade_signal"] = input_payload
    outputs = get_meeting_outputs(meeting["id"], db_path)
    messages = get_meeting_messages(meeting["id"], db_path)
    report_path, markdown = write_markdown_report(
        updated_meeting,
        outputs,
        report_dir,
        messages=messages,
    )
    report = upsert_report(meeting["id"], report_path, markdown, db_path)

    review = create_trade_review(
        ticker=input_payload["ticker"],
        strategy_signal=input_payload["strategy_signal"],
        side=input_payload["side"],
        price=input_payload.get("price"),
        volume=input_payload.get("volume"),
        timeframe=input_payload.get("timeframe"),
        source=input_payload.get("source"),
        input_payload=input_payload,
        structured_decision=council_run.structured_decision,
        linked_meeting_id=meeting["id"],
        db_path=db_path,
    )
    return {
        "trade_review": review,
        "meeting": updated_meeting,
        "outputs": outputs,
        "messages": messages,
        "structured_decision": council_run.structured_decision,
        "order_execution_allowed": False,
        "report": {
            "available": True,
            "path": report["path"],
            "created_at": report["created_at"],
        },
    }


def _normalized_payload(payload: TradeReviewCreate) -> dict[str, Any]:
    data = payload.model_dump()
    data["ticker"] = data["ticker"].strip().upper()
    data["strategy_signal"] = data["strategy_signal"].strip()
    data["side"] = (data.get("side") or "review_only").strip().lower() or "review_only"
    data["timeframe"] = (data.get("timeframe") or "").strip() or None
    data["source"] = (data.get("source") or "").strip() or None
    data["notes"] = (data.get("notes") or "").strip() or None
    data["technical_indicators"] = data.get("technical_indicators") or {}
    data["news_headlines"] = data.get("news_headlines") or []
    data["risk_context"] = data.get("risk_context") or {}
    data["order_execution_allowed"] = False
    data["review_only"] = True
    return data


def _meeting_topic(payload: dict) -> str:
    return (
        f"Read-only trade signal review: {payload['ticker']} "
        f"{payload['strategy_signal']} ({payload['side']})"
    )


def _trade_signal_context_summary(payload: dict) -> str:
    risk_context = payload.get("risk_context") or {}
    indicators = payload.get("technical_indicators") or {}
    news_count = len(payload.get("news_headlines") or [])
    return (
        "Read-only external trade signal review. "
        f"Ticker {payload['ticker']}; strategy signal {payload['strategy_signal']}; "
        f"side '{payload['side']}' is review context only; price {payload.get('price')}; "
        f"volume {payload.get('volume')}; timeframe {payload.get('timeframe')}; "
        f"source {payload.get('source')}. "
        f"Technical indicators: {indicators}. Risk context: {risk_context}. "
        f"News headline count: {news_count}. "
        "AI Council must not create, route, transmit, or execute any order."
    )
