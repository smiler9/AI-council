from __future__ import annotations

from pathlib import Path


def _create_watchlist(client, tickers: list[str] | None = None) -> dict:
    response = client.post(
        "/api/watchlists",
        json={
            "name": "Operations Watchlist",
            "tickers": tickers or ["TESTB", "TESTD"],
            "review_mode": "penny_stock_risk",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_operations_summary_empty_state(client):
    response = client.get("/api/operations/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["counts"]["meetings"] == 0
    assert payload["counts"]["watchlists"] == 0
    assert payload["risk_summary"]["highest_risk_level"] == "low"
    assert payload["provider_status"]["llm_provider"] == "mock"
    assert payload["provider_status"]["market_data_provider"] == "mock_market_data"
    assert payload["provider_status"]["telegram_enabled"] is False
    assert payload["order_execution_allowed"] is False
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in payload["safety_boundary"]


def test_operations_risk_brief_empty_state(client):
    response = client.get("/api/operations/risk-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["danger_items"] == []
    assert payload["warning_items"] == []
    assert payload["need_more_data_items"] == []
    assert payload["allow_items"] == []
    assert payload["summary"]["danger_count"] == 0
    assert payload["order_execution_allowed"] is False


def test_operations_schedule_health_empty_state(client):
    response = client.get("/api/operations/schedule-health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled_schedules"] == 0
    assert payload["disabled_schedules"] == 0
    assert payload["due_schedules"] == 0
    assert payload["last_run_status"] is None
    assert payload["order_execution_allowed"] is False


def test_operations_high_risk_item_aggregation(client):
    watchlist = _create_watchlist(client, ["TESTB", "TESTD"])
    review = client.post(f"/api/watchlists/{watchlist['id']}/run-review")
    assert review.status_code == 201

    summary = client.get("/api/operations/summary")
    brief = client.get("/api/operations/risk-brief?limit=20")

    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["counts"]["watchlist_reviews"] == 1
    assert summary_payload["risk_summary"]["block_count"] >= 1
    assert summary_payload["risk_summary"]["highest_risk_level"] == "critical"
    assert summary_payload["recent_high_risk_items"]
    assert all(item["order_execution_allowed"] is False for item in summary_payload["recent_high_risk_items"])

    assert brief.status_code == 200
    brief_payload = brief.json()
    assert brief_payload["danger_items"]
    tickers = {item["ticker"] for item in brief_payload["danger_items"]}
    assert "TESTD" in tickers
    assert any(item.get("top_risk_event") == "delisting_notice" for item in brief_payload["danger_items"])
    assert brief_payload["summary"]["danger_count"] >= 1
    assert brief_payload["order_execution_allowed"] is False


def test_operations_schedule_run_aggregation(client):
    watchlist = _create_watchlist(client, ["TESTA"])
    schedule = client.post(
        f"/api/watchlists/{watchlist['id']}/schedules",
        json={
            "name": "Operations schedule",
            "enabled": True,
            "cadence": "manual_only",
            "auto_send_telegram": True,
        },
    )
    assert schedule.status_code == 201
    run = client.post(f"/api/watchlist-schedules/{schedule.json()['id']}/run-now")
    assert run.status_code == 200

    health = client.get("/api/operations/schedule-health")
    summary = client.get("/api/operations/summary")

    assert health.status_code == 200
    health_payload = health.json()
    assert health_payload["enabled_schedules"] == 1
    assert health_payload["last_run_status"] == "telegram_disabled"
    assert health_payload["telegram_disabled_count"] == 1
    assert health_payload["recent_runs"][0]["status"] == "telegram_disabled"
    assert health_payload["order_execution_allowed"] is False

    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["counts"]["watchlist_schedules"] == 1
    assert summary_payload["counts"]["schedule_runs"] == 1
    assert summary_payload["recent_schedule_runs"][0]["status"] == "telegram_disabled"


def test_operations_risk_brief_telegram_disabled_safe_handling(client):
    response = client.post("/api/operations/risk-brief/telegram/send")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent"] is False
    assert payload["status"] == "disabled"
    assert payload["order_execution_allowed"] is False
    assert "Order execution allowed: false" in payload["message"]
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in payload["message"]


def test_operations_order_execution_allowed_always_false(client):
    watchlist = _create_watchlist(client, ["TESTD"])
    client.post(f"/api/watchlists/{watchlist['id']}/run-review")

    for path in [
        "/api/operations/summary",
        "/api/operations/risk-brief",
        "/api/operations/schedule-health",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["order_execution_allowed"] is False


def test_operations_code_does_not_add_broker_or_order_execution():
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
