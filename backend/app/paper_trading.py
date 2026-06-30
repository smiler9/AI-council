from __future__ import annotations

from pathlib import Path
from typing import Any

from .council import KOREAN_SAFETY_BOUNDARY
from .market_data import MarketDataConfig, get_market_data_provider
from .repository import (
    create_paper_trade,
    get_autonomous_review,
    get_paper_portfolio,
    get_ticker_review,
    get_trade_review,
    get_watchlist_review,
    get_webhook_event,
    list_paper_positions,
    list_paper_trades,
    update_paper_portfolio,
    upsert_paper_position,
)
from .schemas import PaperSimulationCreate


PAPER_POLICIES = {
    "risk_gate_conservative",
    "observe_only",
    "aggressive_research_only",
}


class PaperSimulationError(ValueError):
    pass


def simulate_review(
    portfolio_id: str,
    payload: PaperSimulationCreate,
    *,
    db_path: str | Path | None,
    market_data_config: MarketDataConfig,
) -> dict:
    portfolio = get_paper_portfolio(portfolio_id, db_path)
    if not portfolio:
        raise PaperSimulationError("Paper portfolio not found")
    if portfolio["status"] != "active":
        raise PaperSimulationError("Paper portfolio is not active")

    candidates = _source_candidates(
        source_type=payload.source_type,
        source_id=payload.source_id,
        db_path=db_path,
    )
    if not candidates:
        raise PaperSimulationError("Review source not found or has no review candidates")

    trades = []
    for candidate in candidates:
        trade = _simulate_candidate(
            portfolio_id=portfolio_id,
            candidate=candidate,
            payload=payload,
            db_path=db_path,
            market_data_config=market_data_config,
        )
        trades.append(trade)

    return {
        "portfolio": get_paper_portfolio(portfolio_id, db_path),
        "source_type": payload.source_type,
        "source_id": payload.source_id,
        "simulation_policy": payload.simulation_policy,
        "trades": trades,
        "positions": list_paper_positions(portfolio_id, db_path),
        "summary": build_paper_summary(
            portfolio_id,
            db_path=db_path,
            market_data_config=market_data_config,
        ),
        "simulation_only": True,
        "paper_trade_execution_allowed": "simulation_only",
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def build_paper_summary(
    portfolio_id: str,
    *,
    db_path: str | Path | None,
    market_data_config: MarketDataConfig,
) -> dict:
    portfolio = get_paper_portfolio(portfolio_id, db_path)
    if not portfolio:
        raise PaperSimulationError("Paper portfolio not found")
    positions = list_paper_positions(portfolio_id, db_path)
    trades = list_paper_trades(portfolio_id, db_path)
    provider = get_market_data_provider(market_data_config)
    exposure = 0.0
    unrealized_pnl = 0.0
    marked_positions = []
    for position in positions:
        market_price = position.get("market_price")
        data_quality = "stored"
        try:
            quote = provider.quote(position["ticker"])
            if quote.get("last_price") is not None:
                market_price = float(quote["last_price"])
                data_quality = quote.get("data_quality") or "limited"
        except Exception:
            data_quality = "limited"
        position_exposure = float(position["quantity"]) * float(market_price or position["average_price"])
        position_unrealized = (
            (float(market_price or position["average_price"]) - float(position["average_price"]))
            * float(position["quantity"])
        )
        exposure += position_exposure
        unrealized_pnl += position_unrealized
        marked_positions.append(
            {
                **position,
                "market_price": market_price,
                "market_data_quality": data_quality,
                "exposure": position_exposure,
                "unrealized_pnl": position_unrealized,
                "order_execution_allowed": False,
            }
        )
    equity = float(portfolio["cash_balance"]) + exposure
    return {
        "portfolio_id": portfolio_id,
        "cash_balance": float(portfolio["cash_balance"]),
        "starting_cash": float(portfolio["starting_cash"]),
        "position_count": len([position for position in positions if position["status"] == "open"]),
        "trade_count": len(trades),
        "recent_trade_count": len(trades[:10]),
        "exposure": exposure,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": sum(float(position.get("realized_pnl") or 0) for position in positions),
        "equity": equity,
        "total_return": equity - float(portfolio["starting_cash"]),
        "positions": marked_positions,
        "data_quality": "limited" if any(p["market_data_quality"] == "limited" for p in marked_positions) else "sufficient",
        "simulation_only": True,
        "paper_trade_execution_allowed": "simulation_only",
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def _simulate_candidate(
    *,
    portfolio_id: str,
    candidate: dict,
    payload: PaperSimulationCreate,
    db_path: str | Path | None,
    market_data_config: MarketDataConfig,
) -> dict:
    portfolio = get_paper_portfolio(portfolio_id, db_path)
    decision = candidate.get("decision") or "NEED_MORE_DATA"
    risk_level = candidate.get("risk_level") or "high"
    policy_result = _policy_result(
        decision=decision,
        risk_level=risk_level,
        policy=payload.simulation_policy,
        allow_only_decision=payload.allow_only_decision,
    )
    price = _simulation_price(candidate, market_data_config)
    ticker = str(candidate.get("ticker") or "UNKNOWN").strip().upper()
    source_type = candidate.get("source_type") or payload.source_type
    source_id = candidate.get("source_id") or payload.source_id

    if policy_result["action"] == "simulated_skip":
        return create_paper_trade(
            portfolio_id=portfolio_id,
            ticker=ticker,
            action="simulated_skip",
            quantity=0.0,
            price=price,
            notional=0.0,
            source_type=source_type,
            source_id=source_id,
            decision=decision,
            risk_level=risk_level,
            simulation_status=policy_result["simulation_status"],
            simulation_policy=payload.simulation_policy,
            notes=policy_result["notes"],
            db_path=db_path,
        )

    if price is None or price <= 0:
        return create_paper_trade(
            portfolio_id=portfolio_id,
            ticker=ticker,
            action="simulated_skip",
            quantity=0.0,
            price=None,
            notional=0.0,
            source_type=source_type,
            source_id=source_id,
            decision=decision,
            risk_level=risk_level,
            simulation_status="skipped_missing_price",
            simulation_policy=payload.simulation_policy,
            notes="No source price or read-only market data quote was available for simulation.",
            db_path=db_path,
        )

    cash_available = float(portfolio["cash_balance"])
    notional = min(float(payload.max_notional_per_trade), cash_available)
    if notional <= 0:
        return create_paper_trade(
            portfolio_id=portfolio_id,
            ticker=ticker,
            action="simulated_skip",
            quantity=0.0,
            price=price,
            notional=0.0,
            source_type=source_type,
            source_id=source_id,
            decision=decision,
            risk_level=risk_level,
            simulation_status="skipped_insufficient_paper_cash",
            simulation_policy=payload.simulation_policy,
            notes="Paper portfolio has no available simulation cash.",
            db_path=db_path,
        )

    quantity = notional / price
    trade = create_paper_trade(
        portfolio_id=portfolio_id,
        ticker=ticker,
        action="simulated_entry",
        quantity=quantity,
        price=price,
        notional=notional,
        source_type=source_type,
        source_id=source_id,
        decision=decision,
        risk_level=risk_level,
        simulation_status="simulated_entry_recorded",
        simulation_policy=payload.simulation_policy,
        notes="Internal paper simulation only. No broker, account, order, or external execution API was used.",
        db_path=db_path,
    )
    update_paper_portfolio(
        portfolio_id,
        cash_balance=cash_available - notional,
        db_path=db_path,
    )
    upsert_paper_position(
        portfolio_id=portfolio_id,
        ticker=ticker,
        quantity_delta=quantity,
        price=price,
        db_path=db_path,
    )
    return trade


def _policy_result(
    *,
    decision: str,
    risk_level: str,
    policy: str,
    allow_only_decision: bool,
) -> dict:
    if policy == "observe_only":
        return {
            "action": "simulated_skip",
            "simulation_status": "observe_only_skip",
            "notes": "Observe-only policy records the review without a paper entry.",
        }
    if allow_only_decision and decision != "ALLOW":
        return {
            "action": "simulated_skip",
            "simulation_status": "skipped_non_allow_decision",
            "notes": "Simulation requested ALLOW-only handling.",
        }
    if policy == "risk_gate_conservative":
        if decision != "ALLOW":
            return {
                "action": "simulated_skip",
                "simulation_status": f"skipped_{decision.lower()}",
                "notes": f"Conservative policy skips {decision} decisions.",
            }
        if risk_level in {"high", "critical"}:
            return {
                "action": "simulated_skip",
                "simulation_status": f"skipped_{risk_level}_risk",
                "notes": "Conservative policy skips high or critical risk even when review says ALLOW.",
            }
        return {
            "action": "simulated_entry",
            "simulation_status": "eligible_for_simulated_entry",
            "notes": "ALLOW with low/medium risk is eligible for internal paper simulation only.",
        }
    if policy == "aggressive_research_only":
        if decision == "ALLOW":
            return {
                "action": "simulated_entry",
                "simulation_status": "eligible_for_simulated_entry",
                "notes": "Research-only policy records an internal simulated entry for ALLOW decisions.",
            }
        return {
            "action": "simulated_skip",
            "simulation_status": f"skipped_{decision.lower()}",
            "notes": f"Research-only policy skips {decision} decisions.",
        }
    raise PaperSimulationError(f"Unsupported simulation policy: {policy}")


def _simulation_price(candidate: dict, market_data_config: MarketDataConfig) -> float | None:
    raw_price = candidate.get("price")
    if raw_price is None:
        market_data = candidate.get("market_data") or {}
        raw_price = market_data.get("last_price") or (market_data.get("quote") or {}).get("last_price")
    try:
        price = float(raw_price)
        if price > 0:
            return price
    except (TypeError, ValueError):
        pass
    ticker = candidate.get("ticker")
    if not ticker:
        return None
    try:
        quote = get_market_data_provider(market_data_config).quote(str(ticker))
        if quote.get("last_price") is not None:
            return float(quote["last_price"])
    except Exception:
        return None
    return None


def _source_candidates(
    *,
    source_type: str,
    source_id: str,
    db_path: str | Path | None,
) -> list[dict]:
    if source_type == "trade_review":
        review = get_trade_review(source_id, db_path)
        return [_trade_review_candidate(review)] if review else []
    if source_type == "ticker_review":
        review = get_ticker_review(source_id, db_path)
        if not review:
            return []
        trade_review = get_trade_review(review["trade_review_id"], db_path)
        return [_ticker_review_candidate(review, trade_review)]
    if source_type == "webhook_event":
        event = get_webhook_event(source_id, db_path)
        if not event:
            return []
        trade_review = get_trade_review(event["trade_review_id"], db_path) if event.get("trade_review_id") else None
        return [_webhook_event_candidate(event, trade_review)]
    if source_type == "autonomous_review":
        review = get_autonomous_review(source_id, db_path)
        return _batch_review_candidates(review, source_type, db_path) if review else []
    if source_type == "watchlist_review":
        review = get_watchlist_review(source_id, db_path)
        return _batch_review_candidates(review, source_type, db_path) if review else []
    return []


def _trade_review_candidate(review: dict | None) -> dict:
    if not review:
        return {}
    payload = review.get("input_payload") or {}
    decision = review.get("structured_decision") or {}
    return {
        "source_type": "trade_review",
        "source_id": review["id"],
        "ticker": review["ticker"],
        "price": payload.get("price") if payload.get("price") is not None else review.get("price"),
        "decision": review.get("decision") or decision.get("decision") or "NEED_MORE_DATA",
        "risk_level": review.get("risk_level") or decision.get("risk_level") or "high",
        "trade_allowed": bool(review.get("trade_allowed", False)),
        "linked_meeting_id": review.get("linked_meeting_id"),
        "order_execution_allowed": False,
    }


def _ticker_review_candidate(review: dict, trade_review: dict | None) -> dict:
    payload = review.get("auto_payload") or {}
    candidate = _trade_review_candidate(trade_review) if trade_review else {}
    return {
        **candidate,
        "source_type": "ticker_review",
        "source_id": review["id"],
        "ticker": review["ticker"],
        "price": payload.get("price") if payload.get("price") is not None else candidate.get("price"),
        "decision": review.get("decision") or candidate.get("decision") or "NEED_MORE_DATA",
        "risk_level": review.get("risk_level") or candidate.get("risk_level") or "high",
        "linked_ticker_review_id": review["id"],
        "linked_trade_review_id": review.get("trade_review_id"),
        "linked_meeting_id": review.get("linked_meeting_id"),
        "order_execution_allowed": False,
    }


def _webhook_event_candidate(event: dict, trade_review: dict | None) -> dict:
    normalized = event.get("normalized_payload") or {}
    candidate = _trade_review_candidate(trade_review) if trade_review else {}
    return {
        **candidate,
        "source_type": "webhook_event",
        "source_id": event["id"],
        "ticker": normalized.get("ticker") or candidate.get("ticker") or "UNKNOWN",
        "price": normalized.get("price") if normalized.get("price") is not None else candidate.get("price"),
        "decision": candidate.get("decision") or "NEED_MORE_DATA",
        "risk_level": candidate.get("risk_level") or "high",
        "linked_trade_review_id": event.get("trade_review_id"),
        "order_execution_allowed": False,
    }


def _batch_review_candidates(
    review: dict,
    source_type: str,
    db_path: str | Path | None,
) -> list[dict]:
    candidates = []
    for item in review.get("results", []):
        price = None
        if item.get("market_data"):
            price = item["market_data"].get("last_price")
        if price is None and item.get("linked_trade_review_id"):
            trade_review = get_trade_review(item["linked_trade_review_id"], db_path)
            if trade_review:
                price = (trade_review.get("input_payload") or {}).get("price")
        candidates.append(
            {
                "source_type": source_type,
                "source_id": review["id"],
                "ticker": item.get("ticker") or "UNKNOWN",
                "price": price,
                "decision": item.get("decision") or "NEED_MORE_DATA",
                "risk_level": item.get("risk_level") or "high",
                "trade_allowed": bool(item.get("trade_allowed", False)),
                "linked_trade_review_id": item.get("linked_trade_review_id"),
                "linked_ticker_review_id": item.get("linked_ticker_review_id"),
                "linked_meeting_id": item.get("linked_meeting_id"),
                "market_data": item.get("market_data") or {},
                "order_execution_allowed": False,
            }
        )
    return candidates
