from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .council import KOREAN_SAFETY_BOUNDARY
from .llm.config import LLMConfig
from .market_data import MarketDataConfig
from .repository import (
    list_autonomous_reviews,
    list_meetings,
    list_paper_portfolios,
    list_paper_positions,
    list_paper_trades,
    list_ticker_reviews,
    list_trade_reviews,
    list_watchlist_reviews,
    list_watchlist_schedule_runs,
    list_watchlist_schedules,
    list_watchlists,
)
from .services.telegram_service import TelegramService
from .webhooks import WebhookConfig
from .watchlist_schedules import is_schedule_due


RISK_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DEFAULT_LIMIT = 20


def build_operations_summary(
    *,
    db_path: str | Path | None,
    llm_config: LLMConfig,
    market_data_config: MarketDataConfig,
    telegram_service: TelegramService,
    webhook_config: WebhookConfig,
) -> dict:
    datasets = _load_datasets(db_path)
    risk_brief = build_operations_risk_brief(db_path=db_path, limit=DEFAULT_LIMIT)
    schedule_health = build_schedule_health(db_path=db_path)
    return {
        "status": "ok",
        "counts": {
            "meetings": len(datasets["meetings"]),
            "trade_reviews": len(datasets["trade_reviews"]),
            "ticker_reviews": len(datasets["ticker_reviews"]),
            "autonomous_reviews": len(datasets["autonomous_reviews"]),
            "watchlists": len(datasets["watchlists"]),
            "watchlist_reviews": len(datasets["watchlist_reviews"]),
            "watchlist_schedules": len(datasets["watchlist_schedules"]),
            "schedule_runs": len(datasets["schedule_runs"]),
            "paper_portfolios": len(datasets["paper_portfolios"]),
            "paper_trades": len(datasets["paper_trades"]),
        },
        "risk_summary": _aggregate_decision_counts(
            _all_risk_items(
                trade_reviews=datasets["trade_reviews"],
                ticker_reviews=datasets["ticker_reviews"],
                autonomous_reviews=datasets["autonomous_reviews"],
                watchlist_reviews=datasets["watchlist_reviews"],
            )
        ),
        "recent_high_risk_items": (risk_brief["danger_items"] + risk_brief["warning_items"])[:8],
        "recent_watchlist_reviews": [
            _watchlist_review_summary(review) for review in datasets["watchlist_reviews"][:5]
        ],
        "recent_schedule_runs": [_schedule_run_summary(run) for run in datasets["schedule_runs"][:5]],
        "schedule_health": schedule_health,
        "paper_summary": _paper_operations_summary(
            datasets["paper_portfolios"],
            datasets["paper_positions"],
            datasets["paper_trades"],
        ),
        "provider_status": {
            "llm_provider": llm_config.provider,
            "market_data_provider": market_data_config.provider,
            "telegram_enabled": telegram_service.config.enabled,
            "telegram_configured": telegram_service.config.configured,
            "webhooks_enabled": webhook_config.enabled,
            "webhooks_require_secret": webhook_config.require_secret,
            "order_execution_allowed": False,
        },
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def build_operations_risk_brief(
    *,
    db_path: str | Path | None,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    limit = _normalize_limit(limit)
    datasets = _load_datasets(db_path)
    items = _all_risk_items(
        trade_reviews=datasets["trade_reviews"],
        ticker_reviews=datasets["ticker_reviews"],
        autonomous_reviews=datasets["autonomous_reviews"],
        watchlist_reviews=datasets["watchlist_reviews"],
    )
    recent = sorted(items, key=lambda item: item.get("created_at") or "", reverse=True)[:limit]
    danger_items = [item for item in recent if _is_danger_item(item)]
    warning_items = [
        item for item in recent if not _is_danger_item(item) and _is_warning_item(item)
    ]
    need_more_data_items = [
        item
        for item in recent
        if item["decision"] == "NEED_MORE_DATA" and not _is_danger_item(item) and not _is_warning_item(item)
    ]
    allow_items = [
        item
        for item in recent
        if item["decision"] == "ALLOW" and not _is_danger_item(item) and not _is_warning_item(item)
    ]
    return {
        "generated_at": _now_iso(),
        "limit": limit,
        "danger_items": danger_items,
        "warning_items": warning_items,
        "need_more_data_items": need_more_data_items,
        "allow_items": allow_items,
        "summary": {
            "danger_count": len(danger_items),
            "warning_count": len(warning_items),
            "need_more_data_count": len(need_more_data_items),
            "allow_count": len(allow_items),
            "order_execution_allowed": False,
        },
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def build_schedule_health(*, db_path: str | Path | None) -> dict:
    schedules = list_watchlist_schedules(db_path)
    runs = list_watchlist_schedule_runs(db_path)
    enabled = [schedule for schedule in schedules if schedule.get("enabled")]
    disabled = [schedule for schedule in schedules if not schedule.get("enabled")]
    current = datetime.now(UTC)
    due = [schedule for schedule in enabled if is_schedule_due(schedule, current)]
    next_upcoming = sorted(
        [schedule for schedule in enabled if schedule.get("next_run_at")],
        key=lambda schedule: schedule.get("next_run_at") or "",
    )[:5]
    return {
        "enabled_schedules": len(enabled),
        "disabled_schedules": len(disabled),
        "due_schedules": len(due),
        "last_run_status": runs[0]["status"] if runs else None,
        "failed_run_count": sum(1 for run in runs if run.get("status") == "failed"),
        "telegram_disabled_count": sum(
            1 for run in runs if run.get("status") == "telegram_disabled"
        ),
        "next_upcoming_runs": [_schedule_summary(schedule) for schedule in next_upcoming],
        "recent_runs": [_schedule_run_summary(run) for run in runs[:5]],
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def send_operations_risk_brief_telegram(
    *,
    db_path: str | Path | None,
    telegram_service: TelegramService,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    brief = build_operations_risk_brief(db_path=db_path, limit=limit)
    message = format_operations_risk_brief_message(brief)
    result = telegram_service.send_message(message)
    return {
        "order_execution_allowed": False,
        **result,
        "message": message,
        "risk_brief": brief,
    }


def format_operations_risk_brief_message(brief: dict) -> str:
    summary = brief.get("summary") or {}
    danger = _telegram_item_lines(brief.get("danger_items", [])[:5])
    warning = _telegram_item_lines(brief.get("warning_items", [])[:5])
    return "\n".join(
        [
            "AI Council Operations Risk Brief",
            f"Generated at: {brief.get('generated_at')}",
            f"Danger: {summary.get('danger_count', 0)}",
            f"Warning: {summary.get('warning_count', 0)}",
            f"Need more data: {summary.get('need_more_data_count', 0)}",
            f"Allow(review-only): {summary.get('allow_count', 0)}",
            "Danger items:",
            danger,
            "Warning items:",
            warning,
            "Order execution allowed: false",
            f"Safety Boundary: {KOREAN_SAFETY_BOUNDARY}",
        ]
    )


def _load_datasets(db_path: str | Path | None) -> dict[str, list[dict]]:
    return {
        "meetings": list_meetings(db_path),
        "trade_reviews": list_trade_reviews(db_path),
        "ticker_reviews": list_ticker_reviews(db_path),
        "autonomous_reviews": list_autonomous_reviews(db_path),
        "watchlists": list_watchlists(db_path),
        "watchlist_reviews": list_watchlist_reviews(db_path),
        "watchlist_schedules": list_watchlist_schedules(db_path),
        "schedule_runs": list_watchlist_schedule_runs(db_path),
        "paper_portfolios": list_paper_portfolios(db_path),
        "paper_positions": _all_paper_positions(db_path),
        "paper_trades": list_paper_trades(db_path=db_path),
    }


def _all_paper_positions(db_path: str | Path | None) -> list[dict]:
    positions = []
    for portfolio in list_paper_portfolios(db_path):
        positions.extend(list_paper_positions(portfolio["id"], db_path))
    return positions


def _paper_operations_summary(
    portfolios: list[dict],
    positions: list[dict],
    trades: list[dict],
) -> dict:
    exposure = sum(
        float(position.get("quantity") or 0)
        * float(position.get("market_price") or position.get("average_price") or 0)
        for position in positions
        if position.get("status") == "open"
    )
    unrealized_pnl = sum(float(position.get("unrealized_pnl") or 0) for position in positions)
    realized_pnl = sum(float(position.get("realized_pnl") or 0) for position in positions)
    cash_balance = sum(float(portfolio.get("cash_balance") or 0) for portfolio in portfolios)
    simulated_exits = [trade for trade in trades if trade.get("action") == "simulated_exit"]
    return {
        "portfolio_count": len(portfolios),
        "recent_trade_count": len(trades[:10]),
        "recent_simulated_exit_count": len(simulated_exits[:10]),
        "total_trade_count": len(trades),
        "open_position_count": len([position for position in positions if position.get("status") == "open"]),
        "virtual_exposure": exposure,
        "total_virtual_equity": cash_balance + exposure,
        "virtual_unrealized_pnl": unrealized_pnl,
        "virtual_realized_pnl": realized_pnl,
        "total_virtual_pnl": unrealized_pnl + realized_pnl,
        "simulation_only": True,
        "paper_trade_execution_allowed": "simulation_only",
        "order_execution_allowed": False,
    }


def _all_risk_items(
    *,
    trade_reviews: list[dict],
    ticker_reviews: list[dict],
    autonomous_reviews: list[dict],
    watchlist_reviews: list[dict],
) -> list[dict]:
    items = []
    items.extend(_trade_review_item(review) for review in trade_reviews)
    items.extend(_ticker_review_item(review) for review in ticker_reviews)
    for review in autonomous_reviews:
        for item in _autonomous_review_items(review):
            items.append(item)
    for review in watchlist_reviews:
        for item in _watchlist_review_items(review):
            items.append(item)
    for item in items:
        item["order_execution_allowed"] = False
    return items


def _trade_review_item(review: dict) -> dict:
    decision = review.get("structured_decision") or {}
    risk_context = (review.get("input_payload") or {}).get("risk_context") or {}
    top_event = risk_context.get("top_risk_event") or {}
    if isinstance(top_event, str):
        top_event = {"event_type": top_event}
    return {
        "source_type": "trade_review",
        "source_id": review["id"],
        "ticker": review["ticker"],
        "decision": review.get("decision") or decision.get("decision") or "NEED_MORE_DATA",
        "risk_level": review.get("risk_level") or decision.get("risk_level") or "high",
        "trade_allowed": bool(review.get("trade_allowed", False)),
        "top_risk_event": top_event.get("event_type"),
        "risk_event_severity": top_event.get("severity"),
        "linked_trade_review_id": review["id"],
        "linked_ticker_review_id": None,
        "linked_meeting_id": review.get("linked_meeting_id"),
        "created_at": review.get("created_at"),
        "data_quality": decision.get("data_quality"),
        "order_execution_allowed": False,
    }


def _ticker_review_item(review: dict) -> dict:
    payload = review.get("auto_payload") or {}
    risk_context = payload.get("risk_context") or {}
    top_event = risk_context.get("top_risk_event") or {}
    if isinstance(top_event, str):
        top_event = {"event_type": top_event}
    return {
        "source_type": "ticker_review",
        "source_id": review["id"],
        "ticker": review["ticker"],
        "decision": review.get("decision") or "NEED_MORE_DATA",
        "risk_level": review.get("risk_level") or "high",
        "trade_allowed": False,
        "top_risk_event": top_event.get("event_type"),
        "risk_event_severity": top_event.get("severity"),
        "linked_trade_review_id": review.get("trade_review_id"),
        "linked_ticker_review_id": review["id"],
        "linked_meeting_id": review.get("linked_meeting_id"),
        "created_at": review.get("created_at"),
        "data_quality": risk_context.get("data_quality"),
        "order_execution_allowed": False,
    }


def _autonomous_review_items(review: dict) -> list[dict]:
    summary = review.get("summary") or {}
    results = summary.get("results") or []
    return [
        {
            "source_type": "autonomous_review",
            "source_id": review["id"],
            "ticker": item.get("ticker"),
            "decision": item.get("decision") or "NEED_MORE_DATA",
            "risk_level": item.get("risk_level") or "high",
            "trade_allowed": bool(item.get("trade_allowed", False)),
            "top_risk_event": _top_event_type(item.get("top_risk_event")),
            "risk_event_severity": item.get("risk_event_severity"),
            "linked_trade_review_id": item.get("linked_trade_review_id"),
            "linked_ticker_review_id": item.get("linked_ticker_review_id"),
            "linked_meeting_id": item.get("linked_meeting_id"),
            "created_at": review.get("created_at"),
            "data_quality": item.get("data_quality"),
            "order_execution_allowed": False,
        }
        for item in results
    ]


def _watchlist_review_items(review: dict) -> list[dict]:
    return [
        {
            "source_type": "watchlist_review",
            "source_id": review["id"],
            "watchlist_id": review.get("watchlist_id"),
            "watchlist_name": review.get("watchlist_name"),
            "ticker": item.get("ticker"),
            "decision": item.get("decision") or "NEED_MORE_DATA",
            "risk_level": item.get("risk_level") or "high",
            "trade_allowed": bool(item.get("trade_allowed", False)),
            "top_risk_event": item.get("top_risk_event"),
            "risk_event_severity": item.get("risk_event_severity"),
            "linked_trade_review_id": item.get("linked_trade_review_id"),
            "linked_ticker_review_id": item.get("linked_ticker_review_id"),
            "linked_meeting_id": item.get("linked_meeting_id"),
            "created_at": review.get("created_at"),
            "data_quality": item.get("data_quality"),
            "order_execution_allowed": False,
        }
        for item in review.get("results", [])
    ]


def _aggregate_decision_counts(items: list[dict]) -> dict:
    summary = {
        "block_count": 0,
        "hold_count": 0,
        "need_more_data_count": 0,
        "allow_count": 0,
        "highest_risk_level": "low",
        "order_execution_allowed": False,
    }
    highest = "low"
    for item in items:
        decision = item.get("decision")
        if decision == "BLOCK":
            summary["block_count"] += 1
        elif decision == "HOLD":
            summary["hold_count"] += 1
        elif decision == "NEED_MORE_DATA":
            summary["need_more_data_count"] += 1
        elif decision == "ALLOW":
            summary["allow_count"] += 1
        risk = item.get("risk_level") or "low"
        if RISK_ORDER.get(risk, 99) < RISK_ORDER.get(highest, 99):
            highest = risk
    summary["highest_risk_level"] = highest
    return summary


def _watchlist_review_summary(review: dict) -> dict:
    return {
        "id": review["id"],
        "watchlist_id": review["watchlist_id"],
        "watchlist_name": review.get("watchlist_name"),
        "ticker_count": review.get("ticker_count"),
        "block_count": review.get("blocked_count", 0),
        "hold_count": review.get("hold_count", 0),
        "need_more_data_count": review.get("need_more_data_count", 0),
        "allow_count": review.get("allow_count", 0),
        "highest_risk_level": review.get("highest_risk_level"),
        "created_at": review.get("created_at"),
        "order_execution_allowed": False,
    }


def _schedule_summary(schedule: dict) -> dict:
    return {
        "id": schedule["id"],
        "watchlist_id": schedule["watchlist_id"],
        "name": schedule["name"],
        "enabled": bool(schedule.get("enabled")),
        "cadence": schedule.get("cadence"),
        "run_time": schedule.get("run_time"),
        "timezone": schedule.get("timezone"),
        "next_run_at": schedule.get("next_run_at"),
        "last_run_at": schedule.get("last_run_at"),
        "auto_send_telegram": bool(schedule.get("auto_send_telegram")),
        "order_execution_allowed": False,
    }


def _schedule_run_summary(run: dict) -> dict:
    return {
        "id": run["id"],
        "schedule_id": run["schedule_id"],
        "watchlist_id": run["watchlist_id"],
        "watchlist_review_id": run.get("watchlist_review_id"),
        "status": run.get("status"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "summary": run.get("summary") or {},
        "telegram_status": run.get("telegram_status") or {},
        "error_message": run.get("error_message"),
        "order_execution_allowed": False,
    }


def _top_event_type(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("event_type")
    if isinstance(value, str):
        return value
    return None


def _is_danger_item(item: dict) -> bool:
    return item.get("decision") == "BLOCK" or item.get("risk_level") == "critical"


def _is_warning_item(item: dict) -> bool:
    return item.get("decision") == "HOLD" or item.get("risk_level") == "high"


def _telegram_item_lines(items: list[dict]) -> str:
    if not items:
        return "- none"
    return "\n".join(
        f"- {item.get('ticker')}: {item.get('decision')} / {item.get('risk_level')} / "
        f"{item.get('top_risk_event') or 'no event'}"
        for item in items
    )


def _normalize_limit(limit: int) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(value, 100))


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
