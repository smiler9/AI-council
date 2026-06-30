from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .council import KOREAN_SAFETY_BOUNDARY
from .market_data import MarketDataConfig
from .paper_trading import PaperSimulationError, build_paper_summary
from .reports import DEFAULT_REPORT_DIR
from .repository import (
    create_paper_performance_report,
    get_autonomous_review,
    get_paper_portfolio,
    get_ticker_review,
    get_trade_review,
    get_watchlist,
    get_watchlist_review,
    get_webhook_event,
    list_paper_positions,
    list_paper_trades,
)


SIMULATION_REPORT_DISCLAIMER = (
    "이 리포트는 내부 가상 시뮬레이션 결과이며 실제 주문, 실제 체결, 실제 투자 성과가 아닙니다."
)


def build_portfolio_performance(
    portfolio_id: str,
    *,
    db_path: str | Path | None,
    market_data_config: MarketDataConfig,
) -> dict:
    portfolio = _portfolio_or_error(portfolio_id, db_path)
    summary = build_paper_summary(
        portfolio_id,
        db_path=db_path,
        market_data_config=market_data_config,
    )
    trades = list_paper_trades(portfolio_id, db_path)
    realized_values = [float(trade.get("realized_pnl") or 0) for trade in trades if trade["action"] == "simulated_exit"]
    wins = [value for value in realized_values if value > 0]
    losses = [value for value in realized_values if value < 0]
    total_pnl = float(summary.get("total_pnl") or 0)
    starting_cash = float(portfolio["starting_cash"])
    return {
        "portfolio_id": portfolio_id,
        "portfolio_name": portfolio["name"],
        "starting_cash": starting_cash,
        "cash_balance": float(portfolio["cash_balance"]),
        "total_position_value": float(summary.get("total_position_value") or 0),
        "total_equity": float(summary.get("total_equity") or 0),
        "realized_pnl": float(summary.get("realized_pnl") or 0),
        "unrealized_pnl": float(summary.get("unrealized_pnl") or 0),
        "total_pnl": total_pnl,
        "total_return_pct": (total_pnl / starting_cash) * 100 if starting_cash > 0 else 0.0,
        "exposure_pct": float(summary.get("exposure_pct") or 0),
        "trade_count": len(trades),
        "entry_count": _count_action(trades, "simulated_entry"),
        "exit_count": _count_action(trades, "simulated_exit"),
        "skip_count": _count_action(trades, "simulated_skip"),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": _ratio(len(wins), len(wins) + len(losses)),
        "average_win": _average(wins),
        "average_loss": _average(losses),
        "profit_factor": _profit_factor(wins, losses),
        "max_single_trade_gain": max(wins) if wins else 0.0,
        "max_single_trade_loss": min(losses) if losses else 0.0,
        "open_position_count": int(summary.get("open_position_count") or 0),
        "closed_position_count": int(summary.get("closed_trade_count") or 0),
        "simulation_only": True,
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def build_performance_by_strategy(
    portfolio_id: str,
    *,
    db_path: str | Path | None,
    market_data_config: MarketDataConfig,
) -> dict:
    trades = _enriched_paper_trades(portfolio_id, db_path)
    positions = build_paper_summary(
        portfolio_id,
        db_path=db_path,
        market_data_config=market_data_config,
    ).get("positions", [])
    groups = _aggregate_trade_groups(
        trades,
        positions,
        key_func=lambda trade: (
            trade["source_type"],
            trade["strategy_signal"],
            trade["simulation_policy"],
        ),
        label_func=lambda key: f"{key[0]} / {key[1]} / {key[2]}",
    )
    for group in groups:
        group["risk_adjusted_note"] = _risk_adjusted_note(group)
    return _group_response(portfolio_id, "by_strategy", groups)


def build_performance_by_decision(
    portfolio_id: str,
    *,
    db_path: str | Path | None,
    market_data_config: MarketDataConfig,
) -> dict:
    trades = _enriched_paper_trades(portfolio_id, db_path)
    positions = build_paper_summary(
        portfolio_id,
        db_path=db_path,
        market_data_config=market_data_config,
    ).get("positions", [])
    groups = _aggregate_trade_groups(
        trades,
        positions,
        key_func=lambda trade: (trade.get("decision_group") or "unknown",),
        label_func=lambda key: key[0],
    )
    for group in groups:
        decision = group["group_key"]
        if decision == "ALLOW":
            group["decision_note"] = "ALLOW는 검토상 허용이며 실제 주문 허용이 아닙니다."
        elif decision in {"HOLD", "BLOCK", "NEED_MORE_DATA"}:
            group["decision_note"] = f"{decision} 결과는 기본적으로 가상 스킵 여부를 확인하는 데 사용됩니다."
        else:
            group["decision_note"] = "원천 판단을 확인할 수 없는 가상 기록입니다."
    return _group_response(portfolio_id, "by_decision", groups)


def build_performance_by_risk_event(
    portfolio_id: str,
    *,
    db_path: str | Path | None,
    market_data_config: MarketDataConfig,
) -> dict:
    trades = _enriched_paper_trades(portfolio_id, db_path)
    positions = build_paper_summary(
        portfolio_id,
        db_path=db_path,
        market_data_config=market_data_config,
    ).get("positions", [])
    expanded = []
    for trade in trades:
        events = trade.get("risk_events") or [{"event_type": "unknown", "severity": "unknown"}]
        for event in events:
            expanded.append(
                {
                    **trade,
                    "risk_event_type": event.get("event_type") or "unknown",
                    "risk_event_severity": event.get("severity") or "unknown",
                }
            )
    groups = _aggregate_trade_groups(
        expanded,
        positions,
        key_func=lambda trade: (trade.get("risk_event_type") or "unknown", trade.get("risk_event_severity") or "unknown"),
        label_func=lambda key: key[0],
    )
    for group in groups:
        group["event_type"] = group["group_key"]
        group["severity"] = group.pop("group_parts")[1]
        group["warning_note"] = _risk_event_warning(group["event_type"], group["severity"])
    return _group_response(portfolio_id, "by_risk_event", groups)


def build_performance_by_watchlist(
    portfolio_id: str,
    *,
    db_path: str | Path | None,
    market_data_config: MarketDataConfig,
) -> dict:
    trades = [
        trade
        for trade in _enriched_paper_trades(portfolio_id, db_path)
        if trade.get("watchlist_id")
    ]
    positions = build_paper_summary(
        portfolio_id,
        db_path=db_path,
        market_data_config=market_data_config,
    ).get("positions", [])
    groups = _aggregate_trade_groups(
        trades,
        positions,
        key_func=lambda trade: (trade["watchlist_id"], trade.get("watchlist_name") or trade["watchlist_id"]),
        label_func=lambda key: key[1],
    )
    for group in groups:
        watchlist_id, watchlist_name = group.pop("group_parts")
        watchlist = get_watchlist(watchlist_id, db_path)
        related = [trade for trade in trades if trade.get("watchlist_id") == watchlist_id]
        group.update(
            {
                "watchlist_id": watchlist_id,
                "watchlist_name": watchlist_name,
                "ticker_count": (watchlist or {}).get("ticker_count", len({trade["ticker"] for trade in related})),
                "high_risk_count": sum(1 for trade in related if trade.get("risk_level") in {"high", "critical"}),
                "block_count": sum(1 for trade in related if trade.get("decision_group") == "BLOCK"),
                "hold_count": sum(1 for trade in related if trade.get("decision_group") == "HOLD"),
                "need_more_data_count": sum(1 for trade in related if trade.get("decision_group") == "NEED_MORE_DATA"),
                "allow_count": sum(1 for trade in related if trade.get("decision_group") == "ALLOW"),
            }
        )
    return _group_response(portfolio_id, "by_watchlist", groups)


def create_performance_report(
    portfolio_id: str,
    *,
    db_path: str | Path | None,
    report_dir: str | Path | None,
    market_data_config: MarketDataConfig,
) -> dict:
    performance = build_portfolio_performance(
        portfolio_id,
        db_path=db_path,
        market_data_config=market_data_config,
    )
    by_strategy = build_performance_by_strategy(
        portfolio_id,
        db_path=db_path,
        market_data_config=market_data_config,
    )
    by_decision = build_performance_by_decision(
        portfolio_id,
        db_path=db_path,
        market_data_config=market_data_config,
    )
    by_risk_event = build_performance_by_risk_event(
        portfolio_id,
        db_path=db_path,
        market_data_config=market_data_config,
    )
    by_watchlist = build_performance_by_watchlist(
        portfolio_id,
        db_path=db_path,
        market_data_config=market_data_config,
    )
    directory = Path(report_dir or DEFAULT_REPORT_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = directory / f"paper_performance_{portfolio_id}_{timestamp}.md"
    markdown = build_performance_markdown(
        performance=performance,
        by_strategy=by_strategy["groups"],
        by_decision=by_decision["groups"],
        by_risk_event=by_risk_event["groups"],
        by_watchlist=by_watchlist["groups"],
    )
    report_path.write_text(markdown, encoding="utf-8")
    report = create_paper_performance_report(
        portfolio_id=portfolio_id,
        path=str(report_path),
        summary={
            "portfolio_id": portfolio_id,
            "portfolio_name": performance["portfolio_name"],
            "total_pnl": performance["total_pnl"],
            "win_rate": performance["win_rate"],
            "trade_count": performance["trade_count"],
            "simulation_only": True,
            "order_execution_allowed": False,
        },
        db_path=db_path,
    )
    return {
        "report": report,
        "path": str(report_path),
        "summary": performance,
        "markdown_preview": markdown[:2000],
        "simulation_only": True,
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def build_performance_markdown(
    *,
    performance: dict,
    by_strategy: list[dict],
    by_decision: list[dict],
    by_risk_event: list[dict],
    by_watchlist: list[dict],
) -> str:
    lines = [
        "# 가상 성과 리포트",
        "",
        SIMULATION_REPORT_DISCLAIMER,
        "",
        "## 포트폴리오 요약",
        "",
        f"- 포트폴리오: `{performance['portfolio_name']}`",
        f"- 시작 현금: `{performance['starting_cash']:.2f}`",
        f"- 총 가상 손익: `{performance['total_pnl']:.2f}`",
        f"- 실현 손익: `{performance['realized_pnl']:.2f}`",
        f"- 평가 손익: `{performance['unrealized_pnl']:.2f}`",
        f"- 승률: `{performance['win_rate']:.2f}%`",
        f"- 평균 수익: `{performance['average_win']:.2f}`",
        f"- 평균 손실: `{performance['average_loss']:.2f}`",
        f"- Profit factor: `{performance['profit_factor']}`",
        "",
        "## 전략별 성과",
        "",
    ]
    _append_groups(lines, by_strategy)
    lines.extend(["## 판단별 성과", ""])
    _append_groups(lines, by_decision)
    lines.extend(["## 리스크 이벤트별 성과", ""])
    _append_groups(lines, by_risk_event)
    lines.extend(["## Watchlist별 성과", ""])
    _append_groups(lines, by_watchlist)
    lines.extend(
        [
            "## 주요 관찰점",
            "",
            "- 성과는 내부 paper trade 기록만 기반으로 계산됩니다.",
            "- `ALLOW`는 검토상 허용이며 실제 주문 허용이 아닙니다.",
            "- 손익은 가상 진입/가상 청산 기록과 mark-to-market 평가를 기반으로 합니다.",
            "",
            "## 한계 및 주의사항",
            "",
            SIMULATION_REPORT_DISCLAIMER,
            "- 외부 브로커 체결, 실제 계좌 잔고, 실제 슬리피지와 연결되지 않습니다.",
            "",
            "## 안전 경계",
            "",
            KOREAN_SAFETY_BOUNDARY,
            "",
            "`simulation_only=true`",
            "`order_execution_allowed=false`",
            "",
        ]
    )
    return "\n".join(lines)


def _append_groups(lines: list[str], groups: list[dict]) -> None:
    if not groups:
        lines.extend(["집계 가능한 가상 거래 기록이 없습니다.", ""])
        return
    for group in groups:
        lines.extend(
            [
                f"### {group.get('group_key') or group.get('event_type') or group.get('watchlist_name')}",
                "",
                f"- 거래 수: `{group['trade_count']}`",
                f"- 가상 진입/청산/스킵: `{group['entry_count']}` / `{group['exit_count']}` / `{group['skip_count']}`",
                f"- 실현 손익: `{group['realized_pnl']:.2f}`",
                f"- 평가 손익: `{group['unrealized_pnl']:.2f}`",
                f"- 총 가상 손익: `{group['total_pnl']:.2f}`",
                f"- 승률: `{group['win_rate']:.2f}%`",
                "",
            ]
        )


def _portfolio_or_error(portfolio_id: str, db_path: str | Path | None) -> dict:
    portfolio = get_paper_portfolio(portfolio_id, db_path)
    if not portfolio:
        raise PaperSimulationError("Paper portfolio not found")
    return portfolio


def _enriched_paper_trades(portfolio_id: str, db_path: str | Path | None) -> list[dict]:
    trades = sorted(list_paper_trades(portfolio_id, db_path), key=lambda item: item.get("created_at") or "")
    enriched = []
    last_entry_by_ticker: dict[str, dict] = {}
    for trade in trades:
        inherited = last_entry_by_ticker.get(trade["ticker"]) if trade["action"] == "simulated_exit" else None
        metadata = _source_metadata(trade, db_path, inherited)
        enriched_trade = {
            **trade,
            **metadata,
            "simulation_policy": (
                inherited.get("simulation_policy")
                if inherited
                else trade.get("simulation_policy") or "unknown"
            ),
            "decision_group": _decision_group(metadata.get("decision") or trade.get("decision")),
            "risk_level": metadata.get("risk_level") or trade.get("risk_level") or "unknown",
            "simulation_only": True,
            "order_execution_allowed": False,
        }
        enriched.append(enriched_trade)
        if trade["action"] == "simulated_entry":
            last_entry_by_ticker[trade["ticker"]] = enriched_trade
    return enriched


def _source_metadata(
    trade: dict,
    db_path: str | Path | None,
    inherited: dict | None = None,
) -> dict:
    if inherited:
        return {
            **{key: inherited.get(key) for key in _METADATA_KEYS},
            "source_type": inherited.get("source_type", trade.get("source_type")),
            "source_id": inherited.get("source_id", trade.get("source_id")),
        }
    source_type = trade.get("source_type")
    source_id = trade.get("source_id")
    if source_type == "trade_review":
        return _trade_review_metadata(get_trade_review(source_id, db_path))
    if source_type == "ticker_review":
        return _ticker_review_metadata(get_ticker_review(source_id, db_path), db_path)
    if source_type == "webhook_event":
        return _webhook_event_metadata(get_webhook_event(source_id, db_path), db_path)
    if source_type == "autonomous_review":
        return _batch_review_metadata(get_autonomous_review(source_id, db_path), trade)
    if source_type == "watchlist_review":
        return _watchlist_review_metadata(get_watchlist_review(source_id, db_path), trade, db_path)
    return _unknown_metadata(source_type=source_type, source_id=source_id, trade=trade)


_METADATA_KEYS = {
    "source_type",
    "source_id",
    "strategy_signal",
    "decision",
    "risk_level",
    "risk_events",
    "top_risk_event",
    "watchlist_id",
    "watchlist_name",
}


def _trade_review_metadata(review: dict | None) -> dict:
    if not review:
        return _unknown_metadata()
    payload = review.get("input_payload") or {}
    risk_context = payload.get("risk_context") or {}
    risk_events = _risk_events_from_context(risk_context)
    return {
        "source_type": "trade_review",
        "source_id": review["id"],
        "strategy_signal": review.get("strategy_signal") or payload.get("strategy_signal") or "unknown",
        "decision": review.get("decision") or (review.get("structured_decision") or {}).get("decision") or "unknown",
        "risk_level": review.get("risk_level") or (review.get("structured_decision") or {}).get("risk_level") or "unknown",
        "risk_events": risk_events,
        "top_risk_event": _top_risk_event(risk_events),
        "watchlist_id": None,
        "watchlist_name": None,
    }


def _ticker_review_metadata(review: dict | None, db_path: str | Path | None) -> dict:
    if not review:
        return _unknown_metadata(source_type="ticker_review")
    payload = review.get("auto_payload") or {}
    trade_meta = _trade_review_metadata(get_trade_review(review.get("trade_review_id"), db_path))
    risk_events = _risk_events_from_context(payload.get("risk_context") or {}) or trade_meta.get("risk_events") or []
    return {
        **trade_meta,
        "source_type": "ticker_review",
        "source_id": review["id"],
        "strategy_signal": payload.get("strategy_signal") or review.get("review_mode") or trade_meta.get("strategy_signal") or "auto_research",
        "decision": review.get("decision") or trade_meta.get("decision") or "unknown",
        "risk_level": review.get("risk_level") or trade_meta.get("risk_level") or "unknown",
        "risk_events": risk_events,
        "top_risk_event": _top_risk_event(risk_events),
    }


def _webhook_event_metadata(event: dict | None, db_path: str | Path | None) -> dict:
    if not event:
        return _unknown_metadata(source_type="webhook_event")
    normalized = event.get("normalized_payload") or {}
    trade_meta = _trade_review_metadata(get_trade_review(event.get("trade_review_id"), db_path))
    risk_events = _risk_events_from_context(normalized.get("risk_context") or {}) or trade_meta.get("risk_events") or []
    return {
        **trade_meta,
        "source_type": "webhook_event",
        "source_id": event["id"],
        "strategy_signal": normalized.get("strategy_signal") or trade_meta.get("strategy_signal") or "webhook_signal",
        "risk_events": risk_events,
        "top_risk_event": _top_risk_event(risk_events),
    }


def _batch_review_metadata(review: dict | None, trade: dict) -> dict:
    if not review:
        return _unknown_metadata(source_type=trade.get("source_type"), source_id=trade.get("source_id"), trade=trade)
    item = _matching_result_item(review.get("results") or (review.get("summary") or {}).get("results") or [], trade.get("ticker"))
    risk_events = item.get("risk_events") or []
    return {
        "source_type": trade.get("source_type"),
        "source_id": review["id"],
        "strategy_signal": review.get("review_mode") or "batch_review",
        "decision": item.get("decision") or trade.get("decision") or "unknown",
        "risk_level": item.get("risk_level") or trade.get("risk_level") or "unknown",
        "risk_events": risk_events,
        "top_risk_event": _top_risk_event(risk_events) or item.get("top_risk_event"),
        "watchlist_id": None,
        "watchlist_name": None,
    }


def _watchlist_review_metadata(review: dict | None, trade: dict, db_path: str | Path | None) -> dict:
    metadata = _batch_review_metadata(review, trade)
    if not review:
        return metadata
    watchlist = get_watchlist(review["watchlist_id"], db_path)
    metadata["watchlist_id"] = review["watchlist_id"]
    metadata["watchlist_name"] = (watchlist or {}).get("name") or review["watchlist_id"]
    return metadata


def _unknown_metadata(
    *,
    source_type: str | None = None,
    source_id: str | None = None,
    trade: dict | None = None,
) -> dict:
    return {
        "source_type": source_type or (trade or {}).get("source_type") or "unknown",
        "source_id": source_id or (trade or {}).get("source_id"),
        "strategy_signal": "unknown",
        "decision": (trade or {}).get("decision") or "unknown",
        "risk_level": (trade or {}).get("risk_level") or "unknown",
        "risk_events": [],
        "top_risk_event": None,
        "watchlist_id": None,
        "watchlist_name": None,
    }


def _aggregate_trade_groups(
    trades: list[dict],
    positions: list[dict],
    *,
    key_func: Callable[[dict], tuple],
    label_func: Callable[[tuple], str],
) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for trade in trades:
        key = key_func(trade)
        if key not in groups:
            groups[key] = _empty_group(key, label_func(key))
        _add_trade_to_group(groups[key], trade)

    unrealized_by_key = _unrealized_by_key(trades, positions, key_func)
    for key, unrealized in unrealized_by_key.items():
        if key not in groups:
            groups[key] = _empty_group(key, label_func(key))
        groups[key]["unrealized_pnl"] += unrealized

    results = []
    for group in groups.values():
        exits = group.pop("_exit_pnls")
        wins = [value for value in exits if value > 0]
        losses = [value for value in exits if value < 0]
        group["total_pnl"] = group["realized_pnl"] + group["unrealized_pnl"]
        group["win_rate"] = _ratio(len(wins), len(wins) + len(losses))
        group["average_pnl"] = _average(exits)
        group["average_win"] = _average(wins)
        group["average_loss"] = _average(losses)
        group["profit_factor"] = _profit_factor(wins, losses)
        group["max_loss"] = min(losses) if losses else 0.0
        group["simulation_only"] = True
        group["order_execution_allowed"] = False
        results.append(group)
    return sorted(results, key=lambda item: (item["group_key"], item["trade_count"]))


def _empty_group(key: tuple, label: str) -> dict:
    return {
        "group_key": label,
        "group_parts": key,
        "trade_count": 0,
        "entry_count": 0,
        "exit_count": 0,
        "skip_count": 0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "total_pnl": 0.0,
        "win_rate": 0.0,
        "average_pnl": 0.0,
        "max_loss": 0.0,
        "_exit_pnls": [],
    }


def _add_trade_to_group(group: dict, trade: dict) -> None:
    group["trade_count"] += 1
    action = trade.get("action")
    if action == "simulated_entry":
        group["entry_count"] += 1
    elif action == "simulated_exit":
        group["exit_count"] += 1
        pnl = float(trade.get("realized_pnl") or 0)
        group["realized_pnl"] += pnl
        group["_exit_pnls"].append(pnl)
    elif action == "simulated_skip":
        group["skip_count"] += 1


def _unrealized_by_key(
    trades: list[dict],
    positions: list[dict],
    key_func: Callable[[dict], tuple],
) -> dict[tuple, float]:
    latest_entry_by_ticker = {}
    for trade in trades:
        if trade.get("action") == "simulated_entry":
            latest_entry_by_ticker[trade["ticker"]] = trade
    unrealized = defaultdict(float)
    for position in positions:
        if position.get("status") != "open":
            continue
        entry = latest_entry_by_ticker.get(position["ticker"])
        if not entry:
            continue
        unrealized[key_func(entry)] += float(position.get("unrealized_pnl") or 0)
    return dict(unrealized)


def _group_response(portfolio_id: str, group_type: str, groups: list[dict]) -> dict:
    return {
        "portfolio_id": portfolio_id,
        "group_type": group_type,
        "groups": groups,
        "simulation_only": True,
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def _risk_events_from_context(context: dict) -> list[dict]:
    events = context.get("risk_events") or []
    if isinstance(events, list):
        normalized = []
        for event in events:
            if isinstance(event, dict):
                normalized.append(
                    {
                        "event_type": event.get("event_type") or event.get("type") or "unknown",
                        "severity": event.get("severity") or "unknown",
                    }
                )
            elif event:
                normalized.append({"event_type": str(event), "severity": "unknown"})
        return normalized
    top_event = context.get("top_risk_event")
    return [{"event_type": top_event, "severity": context.get("risk_event_severity") or "unknown"}] if top_event else []


def _top_risk_event(events: list[dict]) -> str | None:
    if not events:
        return None
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 9}
    top = sorted(events, key=lambda event: severity_order.get(event.get("severity", "unknown"), 9))[0]
    return top.get("event_type")


def _matching_result_item(results: list[dict], ticker: str | None) -> dict:
    for item in results:
        if item.get("ticker") == ticker:
            return item
    return {}


def _decision_group(value: str | None) -> str:
    decision = (value or "unknown").upper()
    return decision if decision in {"ALLOW", "HOLD", "BLOCK", "NEED_MORE_DATA"} else "unknown"


def _risk_adjusted_note(group: dict) -> str:
    if group["total_pnl"] < 0:
        return "가상 손익이 음수입니다. 리스크 조건과 skip 규칙을 재검토하세요."
    if group["entry_count"] == 0:
        return "가상 진입 없이 검토/스킵만 기록된 전략입니다."
    return "내부 가상 성과가 양호해 보이더라도 실제 투자 성과가 아닙니다."


def _risk_event_warning(event_type: str, severity: str) -> str:
    if event_type in {"offering", "reverse_split", "delisting_notice", "trading_halt"}:
        return "Penny stock 리스크 이벤트입니다. 검토상 보수적으로 해석해야 합니다."
    if severity in {"high", "critical"}:
        return "고위험 이벤트로 분류됩니다."
    return "리스크 이벤트 기반 내부 가상 성과 집계입니다."


def _count_action(trades: list[dict], action: str) -> int:
    return sum(1 for trade in trades if trade.get("action") == action)


def _ratio(numerator: int, denominator: int) -> float:
    return (numerator / denominator) * 100 if denominator else 0.0


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _profit_factor(wins: list[float], losses: list[float]) -> float | None:
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss == 0:
        return None if gross_profit == 0 else gross_profit
    return gross_profit / gross_loss
