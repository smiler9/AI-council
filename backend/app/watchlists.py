from __future__ import annotations

import json
from pathlib import Path

from .council import KOREAN_SAFETY_BOUNDARY
from .llm.config import LLMConfig
from .market_data import MarketDataConfig
from .reports import DEFAULT_REPORT_DIR
from .repository import (
    create_watchlist_review,
    get_watchlist,
    get_watchlist_review,
    update_watchlist_review_summary,
)
from .risk_events import RiskEventConfig
from .schemas import TickerReviewCreate
from .services.telegram_service import TelegramService
from .ticker_reviews import run_ticker_review


MAX_WATCHLIST_TICKERS = 50
SOURCE = "watchlist_batch_review"


class WatchlistInputError(ValueError):
    pass


def normalize_tickers(tickers: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for ticker in tickers:
        value = str(ticker or "").strip().upper()
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    if not normalized:
        raise WatchlistInputError("At least one non-empty ticker is required")
    if len(normalized) > MAX_WATCHLIST_TICKERS:
        raise WatchlistInputError(f"Watchlists are limited to {MAX_WATCHLIST_TICKERS} tickers")
    return normalized


def run_watchlist_review(
    watchlist_id: str,
    *,
    db_path: str | Path | None,
    report_dir: str | Path | None,
    llm_config: LLMConfig,
    market_data_config: MarketDataConfig,
    risk_event_config: RiskEventConfig,
) -> dict:
    watchlist = get_watchlist(watchlist_id, db_path)
    if not watchlist:
        raise WatchlistInputError("Watchlist not found")

    results = []
    ticker_review_ids = []
    trade_review_ids = []
    for ticker in watchlist["tickers"]:
        ticker_result = run_ticker_review(
            TickerReviewCreate(
                ticker=ticker,
                review_mode=watchlist["review_mode"],
                timeframe="1d",
                notes=f"Watchlist batch review: {watchlist['name']}",
            ),
            db_path=db_path,
            report_dir=report_dir,
            llm_config=llm_config,
            market_data_config=market_data_config,
            risk_event_config=risk_event_config,
            source=SOURCE,
        )
        ticker_review = ticker_result["ticker_review"]
        trade_review = ticker_result["trade_review"]
        decision = ticker_result["structured_decision"]
        risk_detection = ticker_result.get("risk_events") or {}
        top_event = risk_detection.get("top_event") or {}
        ticker_review_ids.append(ticker_review["id"])
        trade_review_ids.append(trade_review["id"])
        results.append(
            {
                "ticker": ticker,
                "decision": decision["decision"],
                "risk_level": decision["risk_level"],
                "top_risk_event": top_event.get("event_type"),
                "risk_event_severity": top_event.get("severity"),
                "risk_event_decision_impact": risk_detection.get("decision_impact"),
                "trade_allowed": bool(decision.get("trade_allowed", False)),
                "order_execution_allowed": False,
                "data_quality": decision.get("data_quality"),
                "linked_ticker_review_id": ticker_review["id"],
                "linked_trade_review_id": trade_review["id"],
                "linked_meeting_id": trade_review["linked_meeting_id"],
                "risk_events": risk_detection.get("events", []),
                "required_follow_up": decision.get("required_follow_up", [])[:5],
            }
        )

    sorted_results = sort_watchlist_results(results)
    summary = summarize_watchlist_results(sorted_results)
    result_summary = {
        "watchlist_id": watchlist["id"],
        "watchlist_name": watchlist["name"],
        "review_mode": watchlist["review_mode"],
        "ticker_count": len(sorted_results),
        "summary": summary,
        "results": sorted_results,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
        "order_execution_allowed": False,
    }
    review = create_watchlist_review(
        watchlist_id=watchlist["id"],
        review_mode=watchlist["review_mode"],
        ticker_count=len(sorted_results),
        result_summary=result_summary,
        ticker_review_ids=ticker_review_ids,
        trade_review_ids=trade_review_ids,
        highest_risk_level=summary["highest_risk_level"],
        blocked_count=summary["block_count"],
        hold_count=summary["hold_count"],
        need_more_data_count=summary["need_more_data_count"],
        allow_count=summary["allow_count"],
        db_path=db_path,
    )
    report_path = write_watchlist_report(
        review_id=review["id"],
        watchlist=watchlist,
        summary=summary,
        results=sorted_results,
        report_dir=report_dir,
    )
    result_summary["report"] = {
        "available": True,
        "path": str(report_path),
    }
    updated = update_watchlist_review_summary(review["id"], result_summary, db_path)
    return format_watchlist_review_response(updated or review, watchlist)


def format_watchlist_review_response(review: dict, watchlist: dict | None = None) -> dict:
    return {
        "id": review["id"],
        "watchlist_id": review["watchlist_id"],
        "watchlist_name": review.get("watchlist_name") or (watchlist or {}).get("name"),
        "review_mode": review["review_mode"],
        "ticker_count": review["ticker_count"],
        "summary": review.get("summary", {}),
        "results": review.get("results", []),
        "ticker_review_ids": review.get("ticker_review_ids", []),
        "trade_review_ids": review.get("trade_review_ids", []),
        "highest_risk_level": review["highest_risk_level"],
        "blocked_count": review["blocked_count"],
        "hold_count": review["hold_count"],
        "need_more_data_count": review["need_more_data_count"],
        "allow_count": review["allow_count"],
        "report": review.get("report", {}),
        "order_execution_allowed": False,
        "created_at": review["created_at"],
        "safety_boundary": review.get("safety_boundary") or KOREAN_SAFETY_BOUNDARY,
    }


def sort_watchlist_results(results: list[dict]) -> list[dict]:
    decision_order = {"BLOCK": 0, "HOLD": 1, "NEED_MORE_DATA": 2, "ALLOW": 3}
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(
        results,
        key=lambda item: (
            decision_order.get(item.get("decision"), 9),
            risk_order.get(item.get("risk_level"), 9),
            item.get("ticker", ""),
        ),
    )


def summarize_watchlist_results(results: list[dict]) -> dict:
    summary = {
        "allow_count": 0,
        "hold_count": 0,
        "block_count": 0,
        "need_more_data_count": 0,
        "highest_risk_level": "low",
        "order_execution_allowed": False,
        "allow_is_review_only": True,
    }
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    highest = "low"
    for result in results:
        decision = result.get("decision")
        risk_level = result.get("risk_level", "low")
        if decision == "ALLOW":
            summary["allow_count"] += 1
        elif decision == "HOLD":
            summary["hold_count"] += 1
        elif decision == "BLOCK":
            summary["block_count"] += 1
        elif decision == "NEED_MORE_DATA":
            summary["need_more_data_count"] += 1
        if risk_order.get(risk_level, 9) < risk_order.get(highest, 9):
            highest = risk_level
        result["order_execution_allowed"] = False
    summary["highest_risk_level"] = highest
    return summary


def write_watchlist_report(
    *,
    review_id: str,
    watchlist: dict,
    summary: dict,
    results: list[dict],
    report_dir: str | Path | None,
) -> Path:
    directory = Path(report_dir or DEFAULT_REPORT_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    report_path = directory / f"watchlist_review_{review_id}.md"
    report_path.write_text(
        build_watchlist_markdown_report(watchlist=watchlist, summary=summary, results=results),
        encoding="utf-8",
    )
    return report_path


def build_watchlist_markdown_report(*, watchlist: dict, summary: dict, results: list[dict]) -> str:
    sections = [
        "# Watchlist Risk Brief",
        "",
        "## Watchlist 이름",
        "",
        watchlist["name"],
        "",
        "## 분석 종목 수",
        "",
        str(len(results)),
        "",
        "## 전체 요약",
        "",
        "```json",
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False),
        "```",
        "",
    ]
    for title, predicate in [
        ("위험 종목", lambda item: item["decision"] == "BLOCK" or item["risk_level"] == "critical"),
        ("주의 종목", lambda item: item["decision"] == "HOLD" or item["risk_level"] == "high"),
        ("추가 데이터 필요 종목", lambda item: item["decision"] == "NEED_MORE_DATA"),
        ("검토상 허용 종목", lambda item: item["decision"] == "ALLOW"),
    ]:
        grouped = [item for item in results if predicate(item)]
        sections.extend([f"## {title}", ""])
        if grouped:
            for item in grouped:
                sections.append(
                    f"- `{item['ticker']}`: `{item['decision']}` / `{item['risk_level']}` / "
                    f"top event `{item.get('top_risk_event') or 'none'}`"
                )
        else:
            sections.append("해당 종목이 없습니다.")
        sections.append("")
    sections.extend(["## 종목별 판단 요약", ""])
    for item in results:
        sections.extend(
            [
                f"### {item['ticker']}",
                "",
                f"- 판단: `{item['decision']}`",
                f"- 리스크 수준: `{item['risk_level']}`",
                f"- 거래 검토상 허용 여부: `{str(item.get('trade_allowed', False)).lower()}`",
                "- 주문 실행 허용 여부: `false`",
                f"- 데이터 품질: `{item.get('data_quality', 'limited')}`",
                f"- 연결된 회의: `{item.get('linked_meeting_id')}`",
                "",
            ]
        )
    sections.extend(["## 주요 리스크 이벤트", ""])
    event_lines = []
    for item in results:
        for event in item.get("risk_events", []):
            event_lines.append(
                f"- `{item['ticker']}` `{event.get('event_type')}` / `{event.get('severity')}` / "
                f"{'; '.join(event.get('evidence', [])[:2])}"
            )
    sections.extend(event_lines or ["감지된 주요 리스크 이벤트가 없습니다."])
    sections.extend(
        [
            "",
            "## 데이터 품질",
            "",
            "각 종목의 데이터 품질은 ticker review와 risk event detector 결과를 기준으로 표시됩니다.",
            "",
            "## 추가 확인 필요사항",
            "",
        ]
    )
    follow_up = []
    for item in results:
        for value in item.get("required_follow_up", []):
            follow_up.append(f"- `{item['ticker']}`: {value}")
    sections.extend(follow_up[:20] or ["기록된 추가 확인 필요사항이 없습니다."])
    sections.extend(
        [
            "",
            "## 안전 경계",
            "",
            KOREAN_SAFETY_BOUNDARY,
            "",
            "ALLOW는 검토상 허용일 뿐 실제 매수 허용이 아닙니다. AI Council은 주문을 실행하지 않습니다.",
            "",
        ]
    )
    return "\n".join(sections)


def send_watchlist_review_telegram(
    review_id: str,
    *,
    db_path: str | Path | None,
    telegram_service: TelegramService,
) -> dict:
    review = get_watchlist_review(review_id, db_path)
    if not review:
        return {
            "sent": False,
            "status": "not_found",
            "detail": "Watchlist review not found",
            "order_execution_allowed": False,
        }
    message = format_watchlist_telegram_message(review)
    result = telegram_service.send_message(message)
    return {
        "watchlist_review_id": review_id,
        "order_execution_allowed": False,
        **result,
        "message": message,
    }


def format_watchlist_telegram_message(review: dict) -> str:
    summary = review.get("summary") or {}
    top_risks = [
        item
        for item in review.get("results", [])
        if item.get("decision") == "BLOCK" or item.get("risk_level") in {"critical", "high"}
    ][:5]
    top_lines = "\n".join(
        f"- {item['ticker']}: {item['decision']} / {item['risk_level']} / {item.get('top_risk_event') or 'no event'}"
        for item in top_risks
    ) or "- none"
    return "\n".join(
        [
            "AI Council Watchlist Risk Brief",
            f"Watchlist: {review.get('watchlist_name') or review.get('watchlist_id')}",
            f"Tickers: {review.get('ticker_count', 0)}",
            f"BLOCK: {summary.get('block_count', review.get('blocked_count', 0))}",
            f"HOLD: {summary.get('hold_count', review.get('hold_count', 0))}",
            f"NEED_MORE_DATA: {summary.get('need_more_data_count', review.get('need_more_data_count', 0))}",
            f"ALLOW(review-only): {summary.get('allow_count', review.get('allow_count', 0))}",
            f"Highest risk level: {summary.get('highest_risk_level', review.get('highest_risk_level'))}",
            "Top risk tickers:",
            top_lines,
            "Order execution allowed: false",
            f"Safety Boundary: {KOREAN_SAFETY_BOUNDARY}",
        ]
    )
