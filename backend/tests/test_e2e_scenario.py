from pathlib import Path

from app.repository import create_meeting, create_trade_review


DISCLAIMER = "이 리포트는 내부 가상 시뮬레이션 결과이며 실제 주문, 실제 체결, 실제 투자 성과가 아닙니다."


def test_full_e2e_client_scenario(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert _all_order_flags_false(health.json())

    initial_operations = client.get("/api/operations/summary")
    assert initial_operations.status_code == 200
    assert initial_operations.json()["order_execution_allowed"] is False

    watchlist = client.post(
        "/api/watchlists",
        json={
            "name": "E2E Watchlist",
            "description": "Full scenario test",
            "tickers": ["TESTA", "TESTB", "TESTC", "TESTD", "TESTE"],
            "review_mode": "penny_stock_risk",
        },
    )
    assert watchlist.status_code == 201
    watchlist_id = watchlist.json()["id"]

    watchlist_review = client.post(f"/api/watchlists/{watchlist_id}/run-review")
    assert watchlist_review.status_code == 201
    assert watchlist_review.json()["ticker_count"] == 5
    assert watchlist_review.json()["order_execution_allowed"] is False

    risk_events = client.get("/api/risk-events/detect/TESTB")
    assert risk_events.status_code == 200
    event_types = {event["event_type"] for event in risk_events.json()["events"]}
    assert {"offering", "dilution_risk"}.intersection(event_types)
    assert risk_events.json()["order_execution_allowed"] is False

    ticker_review = client.post(
        "/api/ticker-reviews",
        json={"ticker": "TESTB", "review_mode": "penny_stock_risk", "timeframe": "1d"},
    )
    assert ticker_review.status_code == 201
    assert ticker_review.json()["ticker_review"]["id"]
    assert ticker_review.json()["trade_review"]["id"]
    assert ticker_review.json()["order_execution_allowed"] is False

    high_risk_review = client.post(
        "/api/trade-reviews",
        json={
            "ticker": "TESTB",
            "strategy_signal": "e2e_high_spread",
            "side": "review_only",
            "price": 0.47,
            "volume": 850000,
            "timeframe": "1m",
            "source": "backend_e2e_test",
            "news_headlines": [],
            "risk_context": {"spread_pct": 8.4, "premarket": True},
        },
    )
    assert high_risk_review.status_code == 201
    high_risk_review_id = high_risk_review.json()["trade_review"]["id"]
    assert high_risk_review.json()["structured_decision"]["decision"] in {
        "HOLD",
        "BLOCK",
        "NEED_MORE_DATA",
    }

    portfolio = client.post(
        "/api/paper/portfolios",
        json={
            "name": "E2E Paper Portfolio",
            "description": "simulation only",
            "starting_cash": 10000,
        },
    )
    assert portfolio.status_code == 201
    portfolio_id = portfolio.json()["id"]
    assert portfolio.json()["order_execution_allowed"] is False
    assert portfolio.json()["simulation_only"] is True

    skip_simulation = client.post(
        f"/api/paper/portfolios/{portfolio_id}/simulate-review",
        json={
            "source_type": "trade_review",
            "source_id": high_risk_review_id,
            "simulation_policy": "risk_gate_conservative",
            "max_notional_per_trade": 100,
            "slippage_bps": 25,
            "spread_bps": 50,
            "max_spread_pct": 5.0,
        },
    )
    assert skip_simulation.status_code == 201
    assert skip_simulation.json()["trades"][0]["action"] in {"simulated_skip", "simulated_entry"}
    assert skip_simulation.json()["simulation_only"] is True
    assert skip_simulation.json()["order_execution_allowed"] is False

    allow_review = _create_allow_review(client)
    entry_simulation = client.post(
        f"/api/paper/portfolios/{portfolio_id}/simulate-review",
        json={
            "source_type": "trade_review",
            "source_id": allow_review["id"],
            "simulation_policy": "risk_gate_conservative",
            "max_notional_per_trade": 100,
            "slippage_bps": 0,
            "spread_bps": 0,
        },
    )
    assert entry_simulation.status_code == 201
    assert entry_simulation.json()["trades"][0]["action"] == "simulated_entry"

    summary = client.get(f"/api/paper/portfolios/{portfolio_id}/summary")
    positions = client.get(f"/api/paper/portfolios/{portfolio_id}/positions")
    trades = client.get(f"/api/paper/portfolios/{portfolio_id}/trades")
    assert summary.status_code == 200
    assert positions.status_code == 200
    assert trades.status_code == 200
    assert summary.json()["simulation_only"] is True
    assert _all_order_flags_false(summary.json())
    assert _all_order_flags_false(positions.json())
    assert _all_order_flags_false(trades.json())

    open_positions = [position for position in positions.json() if position["status"] == "open"]
    assert open_positions
    exit_response = client.post(
        f"/api/paper/portfolios/{portfolio_id}/positions/{open_positions[0]['id']}/simulate-exit",
        json={
            "exit_reason": "manual_simulated_exit",
            "exit_price": 1.15,
            "slippage_bps": 0,
            "spread_bps": 0,
        },
    )
    assert exit_response.status_code == 200
    assert exit_response.json()["simulation_only"] is True
    assert exit_response.json()["order_execution_allowed"] is False

    evaluate = client.post(
        f"/api/paper/portfolios/{portfolio_id}/evaluate-exits",
        json={"execute_simulated_exits": False},
    )
    assert evaluate.status_code == 200
    assert evaluate.json()["simulation_only"] is True

    performance = client.get(f"/api/paper/portfolios/{portfolio_id}/performance")
    by_strategy = client.get(f"/api/paper/portfolios/{portfolio_id}/performance/by-strategy")
    by_decision = client.get(f"/api/paper/portfolios/{portfolio_id}/performance/by-decision")
    by_risk_event = client.get(f"/api/paper/portfolios/{portfolio_id}/performance/by-risk-event")
    assert performance.status_code == 200
    assert by_strategy.status_code == 200
    assert by_decision.status_code == 200
    assert by_risk_event.status_code == 200
    assert performance.json()["simulation_only"] is True
    assert performance.json()["order_execution_allowed"] is False

    report = client.post(f"/api/paper/portfolios/{portfolio_id}/performance/report")
    assert report.status_code == 200
    report_path = Path(report.json()["path"])
    assert report_path.exists()
    markdown = report_path.read_text(encoding="utf-8")
    assert DISCLAIMER in markdown
    assert "simulation_only=true" in markdown
    assert report.json()["order_execution_allowed"] is False

    operations = client.get("/api/operations/summary")
    assert operations.status_code == 200
    assert operations.json()["counts"]["watchlists"] >= 1
    assert operations.json()["counts"]["paper_portfolios"] >= 1
    assert operations.json()["counts"]["paper_performance_reports"] >= 1
    assert operations.json()["order_execution_allowed"] is False

    brief = client.get("/api/operations/risk-brief")
    schedule_health = client.get("/api/operations/schedule-health")
    telegram = client.post("/api/operations/risk-brief/telegram/send")
    assert brief.status_code == 200
    assert schedule_health.status_code == 200
    assert telegram.status_code == 200
    assert telegram.json()["status"] == "disabled"
    assert telegram.json()["sent"] is False
    assert telegram.json()["order_execution_allowed"] is False


def test_e2e_safety_flags_and_no_broker_order_code(client):
    root = Path(__file__).resolve().parents[1] / "app"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    forbidden_terms = [
        "submit_order",
        "place_order",
        "BrokerClient",
        "OrderRequest",
        "TradingClient",
        "tradeapi.REST",
        "cancel_order",
        "execute_order",
    ]
    for term in forbidden_terms:
        assert term not in source


def _create_allow_review(client) -> dict:
    db_path = client.app.state.db_path
    meeting = create_meeting(
        topic="E2E synthetic ALLOW source",
        ticker="TESTA",
        db_path=db_path,
        mode="risk_gate_review",
    )
    structured_decision = {
        "decision": "ALLOW",
        "confidence": 0.74,
        "risk_level": "low",
        "trade_allowed": True,
        "position_size_multiplier": 0.0,
        "primary_reasons": ["Synthetic ALLOW source for internal paper E2E simulation."],
        "risk_flags": [],
        "required_follow_up": [],
        "data_quality": "sufficient",
        "order_execution_allowed": False,
    }
    return create_trade_review(
        ticker="TESTA",
        strategy_signal="e2e_synthetic_allow",
        side="review_only",
        price=1.0,
        volume=5_000_000,
        timeframe="1m",
        source="backend_e2e_test",
        input_payload={
            "ticker": "TESTA",
            "strategy_signal": "e2e_synthetic_allow",
            "side": "review_only",
            "price": 1.0,
            "volume": 5_000_000,
            "risk_context": {"spread_pct": 1.0},
            "order_execution_allowed": False,
        },
        structured_decision=structured_decision,
        linked_meeting_id=meeting["id"],
        db_path=db_path,
    )


def _all_order_flags_false(value) -> bool:
    if isinstance(value, dict):
        if value.get("order_execution_allowed") is not None and value["order_execution_allowed"] is not False:
            return False
        return all(_all_order_flags_false(item) for item in value.values())
    if isinstance(value, list):
        return all(_all_order_flags_false(item) for item in value)
    return True
