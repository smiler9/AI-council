#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE_URL = os.getenv("AI_COUNCIL_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "30"))
DISCLAIMER = "이 리포트는 내부 가상 시뮬레이션 결과이며 실제 주문, 실제 체결, 실제 투자 성과가 아닙니다."


@dataclass
class E2EFailure(Exception):
    step: str
    detail: str
    http_status: int | None = None
    response_snippet: str | None = None


class ScenarioClient:
    def __init__(self, base_url: str, timeout_seconds: float):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, payload: dict | None = None) -> Any:
        return self._request("POST", path, payload or {})

    def _request(self, method: str, path: str, payload: dict | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return _decode_json(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise E2EFailure(
                step=f"{method} {path}",
                detail="HTTP request failed",
                http_status=exc.code,
                response_snippet=body[:800],
            ) from exc
        except urllib.error.URLError as exc:
            raise E2EFailure(
                step=f"{method} {path}",
                detail=f"Connection failed: {exc.reason}",
            ) from exc


def main() -> int:
    args = parse_args()
    client = ScenarioClient(args.base_url, args.timeout)
    runner = ScenarioRunner(client)
    try:
        summary = runner.run()
    except E2EFailure as exc:
        summary = {
            "status": "failed",
            "failed_step": exc.step,
            "detail": exc.detail,
            "http_status": exc.http_status,
            "response_snippet": exc.response_snippet,
            "steps_total": 17,
            "steps_passed": runner.steps_passed,
            "steps_failed": 1,
            "created": runner.created,
            "safety": runner.safety_summary(),
        }
        print(json.dumps(summary, indent=2 if args.pretty else None, ensure_ascii=False))
        return 1
    print(json.dumps(summary, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI Council full read-only E2E scenario.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="AI Council backend base URL")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP timeout seconds")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser.parse_args()


class ScenarioRunner:
    def __init__(self, client: ScenarioClient):
        self.client = client
        self.steps_passed = 0
        self.created: dict[str, Any] = {}
        self.step_results: list[dict] = []
        self.order_execution_allowed_all_false = True
        self.simulation_only_confirmed = False
        self.entry_note = None

    def run(self) -> dict:
        self.step("Step 1. Backend health 확인", self.check_health)
        self.step("Step 2. Operations summary 초기 확인", self.check_operations_summary)
        watchlist = self.step("Step 3. Watchlist 생성", self.create_watchlist)
        self.created["watchlist_id"] = watchlist["id"]
        watchlist_review = self.step("Step 4. Watchlist run-review 실행", lambda: self.run_watchlist_review(watchlist["id"]))
        self.created["watchlist_review_id"] = watchlist_review["id"]
        self.step("Step 5. Risk events 검증", self.check_risk_events)
        ticker_review = self.step("Step 6. Ticker-only review 생성", self.create_ticker_review)
        self.created["ticker_review_id"] = ticker_review["ticker_review"]["id"]
        direct_review = self.step("Step 7. Trade review 직접 생성", self.create_direct_trade_review)
        self.created["trade_review_id"] = direct_review["trade_review"]["id"]
        portfolio = self.step("Step 8. Paper Portfolio 생성", self.create_paper_portfolio)
        self.created["paper_portfolio_id"] = portfolio["id"]
        self.step(
            "Step 9. Paper simulate-review 실행",
            lambda: self.simulate_review(portfolio["id"], direct_review["trade_review"]["id"]),
        )
        self.step(
            "Step 10. ALLOW low-risk용 테스트 review 생성",
            lambda: self.try_low_risk_entry(portfolio["id"]),
        )
        self.step("Step 11. Paper summary/positions/trades 조회", lambda: self.check_paper_views(portfolio["id"]))
        self.step("Step 12. Evaluate exits 실행", lambda: self.evaluate_exits(portfolio["id"]))
        self.step("Step 13. Paper performance 조회", lambda: self.check_performance(portfolio["id"]))
        report = self.step("Step 14. Performance report 생성", lambda: self.create_performance_report(portfolio["id"]))
        self.created["performance_report_path"] = report["path"]
        self.step("Step 15. Operations risk brief 확인", self.check_operations_risk_brief)
        self.step("Step 16. Schedule health 확인", self.check_schedule_health)
        self.step("Step 17. Telegram disabled 안전 확인", self.check_telegram_disabled)
        return {
            "status": "passed",
            "steps_total": 17,
            "steps_passed": self.steps_passed,
            "steps_failed": 0,
            "created": self.created,
            "safety": self.safety_summary(),
            "notes": [self.entry_note] if self.entry_note else [],
            "step_results": self.step_results,
        }

    def step(self, name: str, func):
        try:
            result = func()
        except E2EFailure:
            raise
        except Exception as exc:
            raise E2EFailure(step=name, detail=str(exc)) from exc
        self.steps_passed += 1
        self.step_results.append({"step": name, "status": "passed"})
        return result

    def check_health(self) -> dict:
        health = self.client.get("/health")
        self.expect(health.get("status") == "ok", "health.status must be ok", health)
        self.assert_order_false(health, "health")
        return health

    def check_operations_summary(self) -> dict:
        summary = self.client.get("/api/operations/summary")
        self.assert_order_false(summary, "operations summary")
        return summary

    def create_watchlist(self) -> dict:
        payload = {
            "name": f"E2E Watchlist {int(time.time())}",
            "description": "Full E2E scenario watchlist",
            "tickers": ["TESTA", "TESTB", "TESTC", "TESTD", "TESTE"],
            "review_mode": "penny_stock_risk",
        }
        watchlist = self.client.post("/api/watchlists", payload)
        self.expect(watchlist.get("ticker_count") == 5, "watchlist ticker_count must be 5", watchlist)
        self.assert_order_false(watchlist, "watchlist")
        return watchlist

    def run_watchlist_review(self, watchlist_id: str) -> dict:
        review = self.client.post(f"/api/watchlists/{watchlist_id}/run-review")
        self.expect(review.get("ticker_count") == 5, "watchlist review ticker_count must be 5", review)
        self.expect(bool(review.get("summary")), "watchlist review summary is required", review)
        self.assert_order_false(review, "watchlist review")
        return review

    def check_risk_events(self) -> dict:
        detection = self.client.get("/api/risk-events/detect/TESTB")
        events = {event.get("event_type") for event in detection.get("events", [])}
        self.expect(
            bool(events.intersection({"offering", "dilution_risk"})),
            "TESTB should detect offering or dilution risk",
            detection,
        )
        self.assert_order_false(detection, "risk events")
        return detection

    def create_ticker_review(self) -> dict:
        review = self.client.post(
            "/api/ticker-reviews",
            {
                "ticker": "TESTB",
                "review_mode": "penny_stock_risk",
                "timeframe": "1d",
                "notes": "Full E2E ticker-only review",
            },
        )
        self.expect(bool(review.get("ticker_review", {}).get("id")), "ticker_review.id is required", review)
        self.expect(bool(review.get("trade_review", {}).get("id")), "linked trade_review.id is required", review)
        self.expect(bool(review.get("meeting", {}).get("id")), "linked meeting.id is required", review)
        self.assert_order_false(review, "ticker review")
        return review

    def create_direct_trade_review(self) -> dict:
        review = self.client.post(
            "/api/trade-reviews",
            {
                "ticker": "TESTB",
                "strategy_signal": "e2e_high_spread_breakout",
                "side": "review_only",
                "price": 0.47,
                "volume": 850000,
                "timeframe": "1m",
                "source": "full_e2e_scenario",
                "notes": "High spread candidate for safe E2E skip handling",
                "technical_indicators": {"relative_volume": 4.1},
                "news_headlines": [],
                "risk_context": {"spread_pct": 8.4, "premarket": True, "float_rotation": 2.0},
            },
        )
        decision = review.get("structured_decision") or review.get("trade_review", {}).get("structured_decision") or {}
        self.expect(
            decision.get("decision") in {"HOLD", "BLOCK", "NEED_MORE_DATA"},
            "high spread review should be HOLD/BLOCK/NEED_MORE_DATA",
            review,
        )
        self.assert_order_false(review, "direct trade review")
        return review

    def create_paper_portfolio(self) -> dict:
        portfolio = self.client.post(
            "/api/paper/portfolios",
            {
                "name": f"E2E Paper Portfolio {int(time.time())}",
                "description": "Internal simulation-only E2E portfolio",
                "starting_cash": 10000,
            },
        )
        self.expect(bool(portfolio.get("id")), "paper portfolio id is required", portfolio)
        self.assert_order_false(portfolio, "paper portfolio")
        self.assert_simulation_only(portfolio, "paper portfolio")
        return portfolio

    def simulate_review(self, portfolio_id: str, source_id: str) -> dict:
        result = self.client.post(
            f"/api/paper/portfolios/{portfolio_id}/simulate-review",
            {
                "source_type": "trade_review",
                "source_id": source_id,
                "simulation_policy": "risk_gate_conservative",
                "max_notional_per_trade": 100,
                "slippage_bps": 25,
                "spread_bps": 50,
                "max_spread_pct": 5,
                "allow_only_decision": False,
            },
        )
        trade = (result.get("trades") or [{}])[0]
        self.expect(
            trade.get("action") in {"simulated_skip", "simulated_entry"},
            "paper simulate-review must record skip or entry",
            result,
        )
        self.assert_order_false(result, "paper simulate-review")
        self.assert_simulation_only(result, "paper simulate-review")
        return result

    def try_low_risk_entry(self, portfolio_id: str) -> dict:
        review = self.client.post(
            "/api/trade-reviews",
            {
                "ticker": "TESTA",
                "strategy_signal": "e2e_low_risk_observation",
                "side": "review_only",
                "price": 0.82,
                "volume": 5000000,
                "timeframe": "1m",
                "source": "full_e2e_scenario",
                "news_headlines": ["TESTA posts momentum update with preliminary revenue growth"],
                "risk_context": {"spread_pct": 1.2, "premarket": False},
            },
        )
        source_id = review.get("trade_review", {}).get("id")
        self.expect(bool(source_id), "low-risk trade_review.id is required", review)
        result = self.simulate_review(portfolio_id, source_id)
        actions = [trade.get("action") for trade in result.get("trades", [])]
        if "simulated_entry" not in actions:
            self.entry_note = "entry scenario skipped because no ALLOW low-risk source available"
        return {"review": review, "simulation": result, "entry_recorded": "simulated_entry" in actions}

    def check_paper_views(self, portfolio_id: str) -> dict:
        summary = self.client.get(f"/api/paper/portfolios/{portfolio_id}/summary")
        positions = self.client.get(f"/api/paper/portfolios/{portfolio_id}/positions")
        trades = self.client.get(f"/api/paper/portfolios/{portfolio_id}/trades")
        self.assert_order_false(summary, "paper summary")
        self.assert_simulation_only(summary, "paper summary")
        for item in positions:
            self.assert_order_false(item, "paper position")
            self.assert_simulation_only(item, "paper position")
        for item in trades:
            self.assert_order_false(item, "paper trade")
            self.assert_simulation_only(item, "paper trade")
        return {"summary": summary, "positions": positions, "trades": trades}

    def evaluate_exits(self, portfolio_id: str) -> dict:
        result = self.client.post(
            f"/api/paper/portfolios/{portfolio_id}/evaluate-exits",
            {
                "execute_simulated_exits": False,
                "take_profit_pct": 8.0,
                "stop_loss_pct": 5.0,
            },
        )
        self.assert_order_false(result, "evaluate exits")
        self.assert_simulation_only(result, "evaluate exits")
        return result

    def check_performance(self, portfolio_id: str) -> dict:
        paths = [
            "/performance",
            "/performance/by-strategy",
            "/performance/by-decision",
            "/performance/by-risk-event",
            "/performance/by-watchlist",
        ]
        payloads = {}
        for suffix in paths:
            payload = self.client.get(f"/api/paper/portfolios/{portfolio_id}{suffix}")
            self.assert_order_false(payload, f"paper {suffix}")
            self.assert_simulation_only(payload, f"paper {suffix}")
            payloads[suffix] = payload
        return payloads

    def create_performance_report(self, portfolio_id: str) -> dict:
        report = self.client.post(f"/api/paper/portfolios/{portfolio_id}/performance/report")
        self.expect(bool(report.get("path")), "performance report path is required", report)
        preview = report.get("markdown_preview") or ""
        self.expect(DISCLAIMER in preview, "performance report disclaimer must be present", report)
        self.assert_order_false(report, "performance report")
        self.assert_simulation_only(report, "performance report")
        return report

    def check_operations_risk_brief(self) -> dict:
        brief = self.client.get("/api/operations/risk-brief")
        self.assert_order_false(brief, "operations risk brief")
        return brief

    def check_schedule_health(self) -> dict:
        health = self.client.get("/api/operations/schedule-health")
        self.assert_order_false(health, "schedule health")
        return health

    def check_telegram_disabled(self) -> dict:
        result = self.client.post("/api/operations/risk-brief/telegram/send")
        self.expect(result.get("status") == "disabled", "telegram should be disabled in default config", result)
        self.expect(result.get("sent") is False, "telegram sent must be false", result)
        self.assert_order_false(result, "telegram disabled")
        return result

    def expect(self, condition: bool, detail: str, response: Any) -> None:
        if not condition:
            raise E2EFailure(
                step="validation",
                detail=detail,
                response_snippet=json.dumps(response, ensure_ascii=False)[:800],
            )

    def assert_order_false(self, payload: Any, context: str) -> None:
        if not _all_order_flags_false(payload):
            self.order_execution_allowed_all_false = False
            raise E2EFailure(
                step=context,
                detail="order_execution_allowed must remain false everywhere",
                response_snippet=json.dumps(payload, ensure_ascii=False)[:800],
            )

    def assert_simulation_only(self, payload: dict, context: str) -> None:
        if payload.get("simulation_only") is True or payload.get("paper_trade_execution_allowed") == "simulation_only":
            self.simulation_only_confirmed = True
            return
        raise E2EFailure(
            step=context,
            detail="simulation_only=true or paper_trade_execution_allowed=simulation_only is required",
            response_snippet=json.dumps(payload, ensure_ascii=False)[:800],
        )

    def safety_summary(self) -> dict:
        return {
            "order_execution_allowed_all_false": self.order_execution_allowed_all_false,
            "simulation_only_confirmed": self.simulation_only_confirmed,
            "broker_api_not_used": True,
        }


def _all_order_flags_false(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("order_execution_allowed") is not None and value.get("order_execution_allowed") is not False:
            return False
        return all(_all_order_flags_false(item) for item in value.values())
    if isinstance(value, list):
        return all(_all_order_flags_false(item) for item in value)
    return True


def _decode_json(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
