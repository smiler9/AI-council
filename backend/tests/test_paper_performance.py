from pathlib import Path

from app.repository import (
    create_meeting,
    create_trade_review,
    create_watchlist,
    create_watchlist_review,
)


def _create_portfolio(client, starting_cash=1000) -> dict:
    response = client.post(
        "/api/paper/portfolios",
        json={
            "name": "Performance Portfolio",
            "description": "internal simulation only",
            "starting_cash": starting_cash,
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_source_review(
    client,
    *,
    ticker="TESTA",
    price=1.0,
    strategy_signal="breakout",
    decision="ALLOW",
    risk_level="low",
    risk_context=None,
) -> dict:
    db_path = client.app.state.db_path
    meeting = create_meeting(
        topic=f"Performance source {ticker}",
        ticker=ticker,
        db_path=db_path,
        mode="risk_gate_review",
    )
    structured_decision = {
        "decision": decision,
        "confidence": 0.7,
        "risk_level": risk_level,
        "trade_allowed": decision == "ALLOW",
        "position_size_multiplier": 0.0,
        "primary_reasons": ["Synthetic performance test review."],
        "risk_flags": [],
        "required_follow_up": [],
        "data_quality": "sufficient",
        "order_execution_allowed": False,
    }
    return create_trade_review(
        ticker=ticker,
        strategy_signal=strategy_signal,
        side="review_only",
        price=price,
        volume=1_000_000,
        timeframe="1m",
        source="paper_performance_test",
        input_payload={
            "ticker": ticker,
            "strategy_signal": strategy_signal,
            "side": "review_only",
            "price": price,
            "risk_context": risk_context or {},
            "order_execution_allowed": False,
        },
        structured_decision=structured_decision,
        linked_meeting_id=meeting["id"],
        db_path=db_path,
    )


def _simulate(client, portfolio_id: str, source_id: str, source_type="trade_review", policy="risk_gate_conservative"):
    response = client.post(
        f"/api/paper/portfolios/{portfolio_id}/simulate-review",
        json={
            "source_type": source_type,
            "source_id": source_id,
            "simulation_policy": policy,
            "max_notional_per_trade": 100,
            "slippage_bps": 0,
            "spread_bps": 0,
            "allow_only_decision": False,
        },
    )
    assert response.status_code == 201
    return response.json()


def _exit_first_position(client, portfolio_id: str, exit_price: float):
    positions = [
        position
        for position in client.get(f"/api/paper/portfolios/{portfolio_id}/positions").json()
        if position["status"] == "open"
    ]
    assert positions
    response = client.post(
        f"/api/paper/portfolios/{portfolio_id}/positions/{positions[0]['id']}/simulate-exit",
        json={
            "exit_reason": "manual_simulated_exit",
            "exit_price": exit_price,
            "slippage_bps": 0,
            "spread_bps": 0,
        },
    )
    assert response.status_code == 200
    return response.json()


def _seed_win_loss_performance(client):
    portfolio = _create_portfolio(client, starting_cash=1000)
    winner = _create_source_review(
        client,
        ticker="TESTA",
        price=1.0,
        strategy_signal="breakout",
        risk_context={"risk_events": [{"event_type": "offering", "severity": "high"}]},
    )
    _simulate(client, portfolio["id"], winner["id"])
    _exit_first_position(client, portfolio["id"], 1.2)

    loser = _create_source_review(
        client,
        ticker="TESTC",
        price=1.0,
        strategy_signal="mean_reversion",
        risk_context={"risk_events": [{"event_type": "reverse_split", "severity": "critical"}]},
    )
    _simulate(client, portfolio["id"], loser["id"])
    _exit_first_position(client, portfolio["id"], 0.9)
    return portfolio


def test_portfolio_performance_summary_calculates_returns_win_rate_and_profit_factor(client):
    portfolio = _seed_win_loss_performance(client)

    response = client.get(f"/api/paper/portfolios/{portfolio['id']}/performance")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trade_count"] == 4
    assert payload["entry_count"] == 2
    assert payload["exit_count"] == 2
    assert round(payload["realized_pnl"], 4) == 10.0
    assert round(payload["total_return_pct"], 4) == 1.0
    assert payload["win_count"] == 1
    assert payload["loss_count"] == 1
    assert payload["win_rate"] == 50.0
    assert round(payload["profit_factor"], 4) == 2.0
    assert payload["simulation_only"] is True
    assert payload["order_execution_allowed"] is False


def test_performance_by_strategy_aggregation(client):
    portfolio = _seed_win_loss_performance(client)

    response = client.get(f"/api/paper/portfolios/{portfolio['id']}/performance/by-strategy")

    assert response.status_code == 200
    groups = response.json()["groups"]
    breakout = next(group for group in groups if "breakout" in group["group_key"])
    assert breakout["entry_count"] == 1
    assert breakout["exit_count"] == 1
    assert round(breakout["realized_pnl"], 4) == 20.0
    assert breakout["simulation_only"] is True


def test_performance_by_decision_tracks_skips(client):
    portfolio = _create_portfolio(client)
    allow = _create_source_review(client, ticker="TESTA", decision="ALLOW", risk_level="low")
    hold = _create_source_review(client, ticker="TESTB", decision="HOLD", risk_level="high")
    _simulate(client, portfolio["id"], allow["id"])
    _simulate(client, portfolio["id"], hold["id"])

    response = client.get(f"/api/paper/portfolios/{portfolio['id']}/performance/by-decision")

    assert response.status_code == 200
    groups = {group["group_key"]: group for group in response.json()["groups"]}
    assert groups["ALLOW"]["entry_count"] == 1
    assert groups["HOLD"]["skip_count"] == 1
    assert groups["HOLD"]["order_execution_allowed"] is False


def test_performance_by_risk_event_aggregation(client):
    portfolio = _seed_win_loss_performance(client)

    response = client.get(f"/api/paper/portfolios/{portfolio['id']}/performance/by-risk-event")

    assert response.status_code == 200
    groups = {group["event_type"]: group for group in response.json()["groups"]}
    assert groups["offering"]["severity"] == "high"
    assert groups["offering"]["entry_count"] == 1
    assert groups["reverse_split"]["severity"] == "critical"
    assert groups["reverse_split"]["order_execution_allowed"] is False


def test_performance_by_watchlist_aggregation(client):
    db_path = client.app.state.db_path
    portfolio = _create_portfolio(client)
    watchlist = create_watchlist(
        name="Performance Watchlist",
        description="watchlist aggregation",
        tickers=["TESTA"],
        review_mode="penny_stock_risk",
        db_path=db_path,
    )
    review = _create_source_review(client, ticker="TESTA", price=1.0, strategy_signal="watchlist_candidate")
    watchlist_review = create_watchlist_review(
        watchlist_id=watchlist["id"],
        review_mode="penny_stock_risk",
        ticker_count=1,
        result_summary={
            "watchlist_id": watchlist["id"],
            "watchlist_name": watchlist["name"],
            "summary": {"allow_count": 1, "order_execution_allowed": False},
            "results": [
                {
                    "ticker": "TESTA",
                    "decision": "ALLOW",
                    "risk_level": "low",
                    "trade_allowed": True,
                    "linked_trade_review_id": review["id"],
                    "risk_events": [],
                    "order_execution_allowed": False,
                }
            ],
            "order_execution_allowed": False,
        },
        ticker_review_ids=[],
        trade_review_ids=[review["id"]],
        highest_risk_level="low",
        blocked_count=0,
        hold_count=0,
        need_more_data_count=0,
        allow_count=1,
        db_path=db_path,
    )
    _simulate(client, portfolio["id"], watchlist_review["id"], source_type="watchlist_review")

    response = client.get(f"/api/paper/portfolios/{portfolio['id']}/performance/by-watchlist")

    assert response.status_code == 200
    groups = response.json()["groups"]
    assert groups[0]["watchlist_id"] == watchlist["id"]
    assert groups[0]["watchlist_name"] == "Performance Watchlist"
    assert groups[0]["allow_count"] >= 1
    assert groups[0]["simulation_only"] is True


def test_performance_report_generation_includes_simulation_disclaimer(client):
    portfolio = _seed_win_loss_performance(client)

    response = client.post(f"/api/paper/portfolios/{portfolio['id']}/performance/report")

    assert response.status_code == 200
    payload = response.json()
    report_path = Path(payload["path"])
    assert report_path.exists()
    markdown = report_path.read_text(encoding="utf-8")
    assert "이 리포트는 내부 가상 시뮬레이션 결과이며 실제 주문, 실제 체결, 실제 투자 성과가 아닙니다." in markdown
    assert "simulation_only=true" in markdown
    assert "order_execution_allowed=false" in markdown
    assert payload["simulation_only"] is True
    assert payload["order_execution_allowed"] is False


def test_paper_performance_order_execution_allowed_always_false(client):
    portfolio = _seed_win_loss_performance(client)
    paths = [
        f"/api/paper/portfolios/{portfolio['id']}/performance",
        f"/api/paper/portfolios/{portfolio['id']}/performance/by-strategy",
        f"/api/paper/portfolios/{portfolio['id']}/performance/by-decision",
        f"/api/paper/portfolios/{portfolio['id']}/performance/by-risk-event",
        f"/api/paper/portfolios/{portfolio['id']}/performance/by-watchlist",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["order_execution_allowed"] is False


def test_paper_performance_code_does_not_add_broker_or_order_execution():
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
