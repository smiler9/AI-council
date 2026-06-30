from __future__ import annotations

from pathlib import Path


def test_watchlist_create(client):
    response = client.post(
        "/api/watchlists",
        json={
            "name": "Penny Stock Watchlist",
            "description": "관심 penny stock 후보군",
            "tickers": ["TESTA", "TESTB"],
            "review_mode": "penny_stock_risk",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Penny Stock Watchlist"
    assert payload["tickers"] == ["TESTA", "TESTB"]
    assert payload["ticker_count"] == 2
    assert payload["order_execution_allowed"] is False


def test_watchlist_ticker_normalization_and_dedup(client):
    response = client.post(
        "/api/watchlists",
        json={
            "name": "Normalize",
            "tickers": [" testa ", "TESTA", "testb", "TestB", "testc"],
            "review_mode": "general_review",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["tickers"] == ["TESTA", "TESTB", "TESTC"]


def test_watchlist_empty_ticker_rejected(client):
    response = client.post(
        "/api/watchlists",
        json={
            "name": "Bad",
            "tickers": ["", "   "],
        },
    )

    assert response.status_code == 422
    assert "ticker" in response.text.lower()


def test_watchlist_list_get_update_delete(client):
    created = client.post(
        "/api/watchlists",
        json={"name": "List", "tickers": ["TESTA", "TESTB"]},
    )
    assert created.status_code == 201
    watchlist_id = created.json()["id"]

    listed = client.get("/api/watchlists")
    detail = client.get(f"/api/watchlists/{watchlist_id}")
    updated = client.patch(
        f"/api/watchlists/{watchlist_id}",
        json={"name": "Updated List", "tickers": ["TESTD", "TESTD", "TESTE"]},
    )
    deleted = client.delete(f"/api/watchlists/{watchlist_id}")
    missing = client.get(f"/api/watchlists/{watchlist_id}")

    assert listed.status_code == 200
    assert any(item["id"] == watchlist_id for item in listed.json())
    assert detail.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated List"
    assert updated.json()["tickers"] == ["TESTD", "TESTE"]
    assert deleted.status_code == 200
    assert deleted.json()["order_execution_allowed"] is False
    assert missing.status_code == 404


def test_watchlist_run_review(client):
    created = client.post(
        "/api/watchlists",
        json={
            "name": "Batch",
            "tickers": ["TESTA", "TESTB", "TESTD"],
            "review_mode": "penny_stock_risk",
        },
    )
    assert created.status_code == 201
    watchlist_id = created.json()["id"]

    response = client.post(f"/api/watchlists/{watchlist_id}/run-review")

    assert response.status_code == 201
    payload = response.json()
    assert payload["watchlist_id"] == watchlist_id
    assert payload["watchlist_name"] == "Batch"
    assert payload["ticker_count"] == 3
    assert len(payload["results"]) == 3
    assert payload["summary"]["highest_risk_level"] == "critical"
    assert payload["summary"]["block_count"] >= 1
    assert payload["order_execution_allowed"] is False
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in payload["safety_boundary"]


def test_watchlist_review_creates_linked_ticker_and_trade_reviews(client):
    created = client.post(
        "/api/watchlists",
        json={"name": "Links", "tickers": ["TESTB", "TESTC"]},
    )
    assert created.status_code == 201

    response = client.post(f"/api/watchlists/{created.json()['id']}/run-review")

    assert response.status_code == 201
    payload = response.json()
    assert len(payload["ticker_review_ids"]) == 2
    assert len(payload["trade_review_ids"]) == 2
    for result in payload["results"]:
        assert result["linked_ticker_review_id"]
        assert result["linked_trade_review_id"]
        assert result["linked_meeting_id"]
        assert result["order_execution_allowed"] is False

    trade_reviews = client.get("/api/trade-reviews").json()
    trade_review_ids = {review["id"] for review in trade_reviews}
    assert set(payload["trade_review_ids"]).issubset(trade_review_ids)


def test_risk_events_reflected_in_watchlist_results(client):
    created = client.post(
        "/api/watchlists",
        json={"name": "Risk Events", "tickers": ["TESTB", "TESTD"]},
    )
    assert created.status_code == 201

    response = client.post(f"/api/watchlists/{created.json()['id']}/run-review")

    assert response.status_code == 201
    payload = response.json()
    by_ticker = {result["ticker"]: result for result in payload["results"]}
    assert by_ticker["TESTB"]["top_risk_event"] in {"offering", "dilution_risk"}
    assert by_ticker["TESTB"]["risk_event_severity"] == "high"
    assert by_ticker["TESTD"]["top_risk_event"] == "delisting_notice"
    assert by_ticker["TESTD"]["risk_event_severity"] == "critical"


def test_watchlist_summary_counts(client):
    created = client.post(
        "/api/watchlists",
        json={"name": "Summary", "tickers": ["TESTA", "TESTB", "TESTC", "TESTD"]},
    )
    assert created.status_code == 201

    response = client.post(f"/api/watchlists/{created.json()['id']}/run-review")

    assert response.status_code == 201
    summary = response.json()["summary"]
    total = (
        summary["allow_count"]
        + summary["hold_count"]
        + summary["block_count"]
        + summary["need_more_data_count"]
    )
    assert total == 4
    assert summary["order_execution_allowed"] is False


def test_watchlist_order_execution_allowed_always_false(client):
    created = client.post(
        "/api/watchlists",
        json={"name": "Safety", "tickers": ["TESTA"]},
    )
    assert created.status_code == 201
    response = client.post(f"/api/watchlists/{created.json()['id']}/run-review")

    assert response.status_code == 201
    payload = response.json()
    assert payload["order_execution_allowed"] is False
    assert all(result["order_execution_allowed"] is False for result in payload["results"])


def test_watchlist_telegram_disabled_safe_handling(client):
    created = client.post(
        "/api/watchlists",
        json={"name": "Telegram", "tickers": ["TESTA"]},
    )
    assert created.status_code == 201
    review = client.post(f"/api/watchlists/{created.json()['id']}/run-review")
    assert review.status_code == 201

    response = client.post(f"/api/watchlist-reviews/{review.json()['id']}/telegram/send")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent"] is False
    assert payload["status"] == "disabled"
    assert payload["order_execution_allowed"] is False
    assert "Order execution allowed: false" in payload["message"]


def test_watchlist_report_generation(client):
    created = client.post(
        "/api/watchlists",
        json={"name": "Report", "tickers": ["TESTB", "TESTD"]},
    )
    assert created.status_code == 201

    response = client.post(f"/api/watchlists/{created.json()['id']}/run-review")

    assert response.status_code == 201
    report = response.json()["report"]
    assert report["available"] is True
    report_path = Path(report["path"])
    assert report_path.exists()
    markdown = report_path.read_text(encoding="utf-8")
    assert "# Watchlist Risk Brief" in markdown
    assert "## 위험 종목" in markdown
    assert "## 주요 리스크 이벤트" in markdown
    assert "## 안전 경계" in markdown
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in markdown


def test_watchlist_review_list_get(client):
    created = client.post(
        "/api/watchlists",
        json={"name": "Review List", "tickers": ["TESTA"]},
    )
    assert created.status_code == 201
    review = client.post(f"/api/watchlists/{created.json()['id']}/run-review")
    assert review.status_code == 201
    review_id = review.json()["id"]

    listed = client.get("/api/watchlist-reviews")
    detail = client.get(f"/api/watchlist-reviews/{review_id}")

    assert listed.status_code == 200
    assert any(item["id"] == review_id for item in listed.json())
    assert detail.status_code == 200
    assert detail.json()["id"] == review_id
    assert detail.json()["order_execution_allowed"] is False


def test_watchlist_code_does_not_add_broker_or_order_execution():
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
