from pathlib import Path

from app.repository import create_meeting, create_trade_review


def _create_portfolio(client, starting_cash=1000) -> dict:
    response = client.post(
        "/api/paper/portfolios",
        json={
            "name": "Paper Test Portfolio",
            "description": "Simulation only",
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
    decision="ALLOW",
    risk_level="low",
) -> dict:
    db_path = client.app.state.db_path
    meeting = create_meeting(
        topic=f"Synthetic paper source {ticker}",
        ticker=ticker,
        db_path=db_path,
        mode="risk_gate_review",
    )
    structured_decision = {
        "decision": decision,
        "confidence": 0.72,
        "risk_level": risk_level,
        "trade_allowed": decision == "ALLOW",
        "position_size_multiplier": 0.0,
        "primary_reasons": ["Synthetic review for paper simulation tests."],
        "risk_flags": [],
        "required_follow_up": [],
        "data_quality": "sufficient",
        "order_execution_allowed": False,
    }
    return create_trade_review(
        ticker=ticker,
        strategy_signal="synthetic_review",
        side="review_only",
        price=price,
        volume=1_000_000,
        timeframe="1m",
        source="paper_test",
        input_payload={
            "ticker": ticker,
            "strategy_signal": "synthetic_review",
            "side": "review_only",
            "price": price,
            "volume": 1_000_000,
            "order_execution_allowed": False,
        },
        structured_decision=structured_decision,
        linked_meeting_id=meeting["id"],
        db_path=db_path,
    )


def _simulate(client, portfolio_id: str, source_id: str, policy="risk_gate_conservative"):
    return client.post(
        f"/api/paper/portfolios/{portfolio_id}/simulate-review",
        json={
            "source_type": "trade_review",
            "source_id": source_id,
            "simulation_policy": policy,
            "max_notional_per_trade": 100,
            "allow_only_decision": False,
        },
    )


def test_paper_portfolio_create_list_get_update_delete(client):
    portfolio = _create_portfolio(client, starting_cash=5000)

    list_response = client.get("/api/paper/portfolios")
    detail_response = client.get(f"/api/paper/portfolios/{portfolio['id']}")
    update_response = client.patch(
        f"/api/paper/portfolios/{portfolio['id']}",
        json={"name": "Updated Paper Portfolio", "status": "archived"},
    )
    delete_response = client.delete(f"/api/paper/portfolios/{portfolio['id']}")

    assert any(item["id"] == portfolio["id"] for item in list_response.json())
    assert detail_response.json()["portfolio"]["starting_cash"] == 5000
    assert detail_response.json()["order_execution_allowed"] is False
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Paper Portfolio"
    assert update_response.json()["status"] == "archived"
    assert delete_response.status_code == 200
    assert delete_response.json()["order_execution_allowed"] is False


def test_simulate_review_block_results_in_simulated_skip(client):
    portfolio = _create_portfolio(client)
    review = _create_source_review(client, decision="BLOCK", risk_level="critical")

    response = _simulate(client, portfolio["id"], review["id"])

    assert response.status_code == 201
    trade = response.json()["trades"][0]
    assert trade["action"] == "simulated_skip"
    assert trade["simulation_status"] == "skipped_block"
    assert trade["order_execution_allowed"] is False


def test_simulate_review_hold_results_in_simulated_skip(client):
    portfolio = _create_portfolio(client)
    review = _create_source_review(client, decision="HOLD", risk_level="high")

    response = _simulate(client, portfolio["id"], review["id"])

    assert response.status_code == 201
    trade = response.json()["trades"][0]
    assert trade["action"] == "simulated_skip"
    assert trade["simulation_status"] == "skipped_hold"


def test_simulate_review_need_more_data_results_in_simulated_skip(client):
    portfolio = _create_portfolio(client)
    review = _create_source_review(client, decision="NEED_MORE_DATA", risk_level="medium")

    response = _simulate(client, portfolio["id"], review["id"])

    assert response.status_code == 201
    trade = response.json()["trades"][0]
    assert trade["action"] == "simulated_skip"
    assert trade["simulation_status"] == "skipped_need_more_data"


def test_simulate_review_allow_low_risk_creates_simulated_entry(client):
    portfolio = _create_portfolio(client, starting_cash=1000)
    review = _create_source_review(client, ticker="TESTA", price=2.0, decision="ALLOW", risk_level="low")

    response = _simulate(client, portfolio["id"], review["id"])

    assert response.status_code == 201
    payload = response.json()
    trade = payload["trades"][0]
    assert trade["action"] == "simulated_entry"
    assert trade["simulation_status"] == "simulated_entry_recorded"
    assert trade["notional"] == 100
    assert trade["order_execution_allowed"] is False
    assert payload["summary"]["cash_balance"] == 900
    assert payload["summary"]["position_count"] == 1
    assert payload["paper_trade_execution_allowed"] == "simulation_only"


def test_missing_price_results_in_skipped_missing_price(client):
    portfolio = _create_portfolio(client)
    review = _create_source_review(
        client,
        ticker="UNKNOWN",
        price=None,
        decision="ALLOW",
        risk_level="low",
    )

    response = _simulate(client, portfolio["id"], review["id"])

    assert response.status_code == 201
    trade = response.json()["trades"][0]
    assert trade["action"] == "simulated_skip"
    assert trade["simulation_status"] == "skipped_missing_price"
    assert trade["price"] is None


def test_position_and_cash_balance_update_on_multiple_entries(client):
    portfolio = _create_portfolio(client, starting_cash=1000)
    first = _create_source_review(client, ticker="TESTA", price=1.0, decision="ALLOW", risk_level="medium")
    second = _create_source_review(client, ticker="TESTA", price=2.0, decision="ALLOW", risk_level="medium")

    first_response = _simulate(client, portfolio["id"], first["id"])
    second_response = _simulate(client, portfolio["id"], second["id"])
    positions = client.get(f"/api/paper/portfolios/{portfolio['id']}/positions").json()
    trades = client.get(f"/api/paper/portfolios/{portfolio['id']}/trades").json()
    summary = client.get(f"/api/paper/portfolios/{portfolio['id']}/summary").json()

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert len(positions) == 1
    assert round(positions[0]["quantity"], 4) == 150.0
    assert round(positions[0]["average_price"], 4) == 1.3333
    assert len(trades) == 2
    assert summary["cash_balance"] == 800
    assert summary["position_count"] == 1
    assert summary["order_execution_allowed"] is False


def test_observe_only_policy_records_simulated_skip(client):
    portfolio = _create_portfolio(client)
    review = _create_source_review(client, decision="ALLOW", risk_level="low")

    response = _simulate(client, portfolio["id"], review["id"], policy="observe_only")

    assert response.status_code == 201
    trade = response.json()["trades"][0]
    assert trade["action"] == "simulated_skip"
    assert trade["simulation_status"] == "observe_only_skip"


def test_paper_order_execution_allowed_always_false(client):
    portfolio = _create_portfolio(client)
    review = _create_source_review(client, decision="ALLOW", risk_level="low")
    client.post(
        f"/api/paper/portfolios/{portfolio['id']}/simulate-review",
        json={
            "source_type": "trade_review",
            "source_id": review["id"],
            "simulation_policy": "aggressive_research_only",
            "max_notional_per_trade": 50,
        },
    )

    paths = [
        "/api/paper/portfolios",
        f"/api/paper/portfolios/{portfolio['id']}",
        f"/api/paper/portfolios/{portfolio['id']}/positions",
        f"/api/paper/portfolios/{portfolio['id']}/trades",
        f"/api/paper/portfolios/{portfolio['id']}/summary",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        if isinstance(payload, list):
            assert all(item["order_execution_allowed"] is False for item in payload)
        else:
            assert payload["order_execution_allowed"] is False


def test_paper_code_does_not_add_broker_or_order_execution():
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
