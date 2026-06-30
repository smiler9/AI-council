from __future__ import annotations

from pathlib import Path

from .council import KOREAN_SAFETY_BOUNDARY
from .llm.config import LLMConfig
from .market_data import MarketDataConfig, get_market_data_provider
from .repository import create_autonomous_review, get_autonomous_review
from .risk_events import RiskEventConfig
from .schemas import AutonomousReviewCreate, TickerReviewCreate
from .services.telegram_service import TelegramService
from .ticker_reviews import run_ticker_review


SOURCE = "autonomous_trader_review"


class MockCandidateScanner:
    name = "mock_market_data"

    def scan(self, universe: str, review_mode: str, max_candidates: int, timeframe: str) -> list[dict]:
        from .market_data import MockMarketDataProvider

        return MockMarketDataProvider().scan_candidates(
            universe=universe,
            review_mode=review_mode,
            max_candidates=max_candidates,
            timeframe=timeframe,
        )


def run_autonomous_review(
    payload: AutonomousReviewCreate,
    *,
    db_path: str | Path | None,
    report_dir: str | Path | None,
    llm_config: LLMConfig,
    market_data_config: MarketDataConfig,
    risk_event_config: RiskEventConfig | None = None,
) -> dict:
    timeframe = payload.timeframe.strip() or "1d"
    provider = get_market_data_provider(market_data_config)
    candidates = provider.scan_candidates(
        universe=payload.universe,
        review_mode=payload.review_mode,
        max_candidates=payload.max_candidates,
        timeframe=timeframe,
    )
    results = []
    ticker_review_ids = []
    trade_review_ids = []
    for candidate in candidates:
        candidate_result = run_ticker_review(
            TickerReviewCreate(
                ticker=candidate["ticker"],
                review_mode=payload.review_mode,
                timeframe=timeframe,
                notes=payload.notes or "자율 후보 발굴 및 검토",
            ),
            db_path=db_path,
            report_dir=report_dir,
            llm_config=llm_config,
            market_data_config=market_data_config,
            risk_event_config=risk_event_config,
            market_data_override=candidate,
            source=SOURCE,
        )
        ticker_review = candidate_result["ticker_review"]
        trade_review = candidate_result["trade_review"]
        decision = candidate_result["structured_decision"]
        risk_detection = candidate_result.get("risk_events") or {}
        top_event = risk_detection.get("top_event") or {}
        ticker_review_ids.append(ticker_review["id"])
        trade_review_ids.append(trade_review["id"])
        results.append(
            {
                "ticker": candidate["ticker"],
                "decision": decision["decision"],
                "risk_level": decision["risk_level"],
                "trade_allowed": bool(decision.get("trade_allowed", False)),
                "order_execution_allowed": False,
                "scan_reason": candidate["scan_reason"],
                "linked_trade_review_id": trade_review["id"],
                "linked_ticker_review_id": ticker_review["id"],
                "linked_meeting_id": trade_review["linked_meeting_id"],
                "data_quality": candidate.get("data_quality", "limited"),
                "risk_events": risk_detection.get("events", []),
                "top_risk_event": top_event,
                "risk_event_severity": top_event.get("severity"),
                "risk_event_decision_impact": risk_detection.get("decision_impact"),
                "market_data": candidate,
            }
        )
    sorted_results = sort_autonomous_results(results)
    summary = summarize_autonomous_results(sorted_results)
    review = create_autonomous_review(
        universe=payload.universe,
        review_mode=payload.review_mode,
        max_candidates=payload.max_candidates,
        timeframe=timeframe,
        candidate_count=len(sorted_results),
        result_summary={
            **summary,
            "results": sorted_results,
            "safety_boundary": KOREAN_SAFETY_BOUNDARY,
            "order_execution_allowed": False,
        },
        created_trade_review_ids=trade_review_ids,
        created_ticker_review_ids=ticker_review_ids,
        db_path=db_path,
    )
    return {
        "id": review["id"],
        "universe": review["universe"],
        "review_mode": review["review_mode"],
        "timeframe": review["timeframe"],
        "candidate_count": review["candidate_count"],
        "results": sorted_results,
        "summary": summary,
        "created_trade_review_ids": trade_review_ids,
        "created_ticker_review_ids": ticker_review_ids,
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def sort_autonomous_results(results: list[dict]) -> list[dict]:
    decision_order = {
        "BLOCK": 0,
        "HOLD": 1,
        "NEED_MORE_DATA": 2,
        "ALLOW": 3,
    }
    risk_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }
    return sorted(
        results,
        key=lambda item: (
            decision_order.get(item.get("decision"), 9),
            risk_order.get(item.get("risk_level"), 9),
            item.get("ticker", ""),
        ),
    )


def summarize_autonomous_results(results: list[dict]) -> dict:
    summary = {
        "allow_count": 0,
        "hold_count": 0,
        "block_count": 0,
        "need_more_data_count": 0,
        "critical_count": 0,
        "high_count": 0,
        "order_execution_allowed": False,
        "allow_is_review_only": True,
    }
    for result in results:
        decision = result.get("decision")
        if decision == "ALLOW":
            summary["allow_count"] += 1
        elif decision == "HOLD":
            summary["hold_count"] += 1
        elif decision == "BLOCK":
            summary["block_count"] += 1
        elif decision == "NEED_MORE_DATA":
            summary["need_more_data_count"] += 1
        if result.get("risk_level") == "critical":
            summary["critical_count"] += 1
        if result.get("risk_level") == "high":
            summary["high_count"] += 1
        result["order_execution_allowed"] = False
    return summary


def send_autonomous_review_telegram(
    review_id: str,
    *,
    db_path: str | Path | None,
    telegram_service: TelegramService,
) -> dict:
    review = get_autonomous_review(review_id, db_path)
    if not review:
        return {
            "sent": False,
            "status": "not_found",
            "detail": "Autonomous review not found",
            "order_execution_allowed": False,
        }
    message = format_autonomous_review_message(review)
    result = telegram_service.send_message(message)
    return {
        "autonomous_review_id": review_id,
        "order_execution_allowed": False,
        **result,
        "message": message,
    }


def format_autonomous_review_message(review: dict) -> str:
    summary = review.get("summary") or {}
    return "\n".join(
        [
            "AI Council Autonomous Trader Review",
            f"Universe: {review.get('universe')}",
            f"Review mode: {review.get('review_mode')}",
            f"Candidates: {review.get('candidate_count')}",
            f"ALLOW(review-only): {summary.get('allow_count', 0)}",
            f"HOLD: {summary.get('hold_count', 0)}",
            f"BLOCK: {summary.get('block_count', 0)}",
            f"NEED_MORE_DATA: {summary.get('need_more_data_count', 0)}",
            "Order execution allowed: false",
            f"Safety Boundary: {KOREAN_SAFETY_BOUNDARY}",
        ]
    )
