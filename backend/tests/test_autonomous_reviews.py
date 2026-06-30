from __future__ import annotations

from pathlib import Path

from app.autonomous_reviews import MockCandidateScanner, summarize_autonomous_results


def test_autonomous_review_create(client):
    response = client.post(
        "/api/autonomous-reviews",
        json={
            "universe": "mock_penny_stocks",
            "review_mode": "penny_stock_risk",
            "max_candidates": 3,
            "timeframe": "1d",
            "notes": "자율 후보 발굴 및 검토",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["universe"] == "mock_penny_stocks"
    assert payload["review_mode"] == "penny_stock_risk"
    assert payload["candidate_count"] == 3
    assert len(payload["results"]) == 3
    assert payload["order_execution_allowed"] is False
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in payload["safety_boundary"]


def test_mock_scanner_generates_candidates():
    scanner = MockCandidateScanner()

    candidates = scanner.scan("mock_penny_stocks", "penny_stock_risk", 5, "1d")

    assert [candidate["ticker"] for candidate in candidates] == [
        "TESTA",
        "TESTB",
        "TESTC",
        "TESTD",
        "TESTE",
    ]
    assert all("scan_reason" in candidate for candidate in candidates)
    assert all(candidate["provider"] == "mock_market_data" for candidate in candidates)


def test_autonomous_review_respects_max_candidates(client):
    response = client.post(
        "/api/autonomous-reviews",
        json={"universe": "mock_penny_stocks", "max_candidates": 2},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["candidate_count"] == 2
    assert len(payload["results"]) == 2
    assert len(payload["created_trade_review_ids"]) == 2
    assert len(payload["created_ticker_review_ids"]) == 2


def test_autonomous_candidates_link_to_trade_and_ticker_reviews(client):
    response = client.post(
        "/api/autonomous-reviews",
        json={"universe": "mock_watchlist", "max_candidates": 2},
    )

    assert response.status_code == 201
    payload = response.json()
    for result in payload["results"]:
        assert result["linked_trade_review_id"]
        assert result["linked_ticker_review_id"]
        assert result["linked_meeting_id"]
        assert result["order_execution_allowed"] is False

    trade_reviews = client.get("/api/trade-reviews")
    assert trade_reviews.status_code == 200
    review_ids = {review["id"] for review in trade_reviews.json()}
    assert set(payload["created_trade_review_ids"]).issubset(review_ids)


def test_autonomous_order_execution_allowed_always_false(client):
    response = client.post(
        "/api/autonomous-reviews",
        json={"universe": "mock_penny_stocks", "max_candidates": 4},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["order_execution_allowed"] is False
    assert payload["summary"]["order_execution_allowed"] is False
    assert all(result["order_execution_allowed"] is False for result in payload["results"])


def test_allow_decision_is_review_only_not_order_permission():
    results = [
        {
            "ticker": "TESTALLOW",
            "decision": "ALLOW",
            "risk_level": "low",
            "trade_allowed": True,
            "order_execution_allowed": True,
        }
    ]

    summary = summarize_autonomous_results(results)

    assert summary["allow_count"] == 1
    assert summary["allow_is_review_only"] is True
    assert summary["order_execution_allowed"] is False
    assert results[0]["order_execution_allowed"] is False


def test_autonomous_telegram_disabled_safe_handling(client):
    created = client.post(
        "/api/autonomous-reviews",
        json={"universe": "custom_stub", "max_candidates": 1},
    )
    assert created.status_code == 201
    review_id = created.json()["id"]

    response = client.post(f"/api/autonomous-reviews/{review_id}/telegram/send")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent"] is False
    assert payload["status"] == "disabled"
    assert payload["order_execution_allowed"] is False
    assert "Order execution allowed: false" in payload["message"]


def test_autonomous_review_code_does_not_add_broker_or_order_execution():
    root = Path(__file__).resolve().parents[1] / "app"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    forbidden_terms = [
        "submit_order",
        "place_order",
        "BrokerClient",
        "OrderRequest",
        "TradingClient",
        "tradeapi.REST",
    ]
    for term in forbidden_terms:
        assert term not in source
