from __future__ import annotations

from pathlib import Path

from app.market_data import MockMarketDataProvider
from app.schemas import TickerReviewCreate
from app.ticker_reviews import build_auto_research_payload


def test_ticker_only_review_create(client):
    response = client.post(
        "/api/ticker-reviews",
        json={"ticker": "TESTA"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["ticker_review"]["ticker"] == "TESTA"
    assert payload["ticker_review"]["review_mode"] == "penny_stock_risk"
    assert payload["trade_review"]["ticker"] == "TESTA"
    assert payload["trade_review"]["side"] == "review_only"
    assert payload["structured_decision"]["decision"] in {
        "ALLOW",
        "HOLD",
        "BLOCK",
        "NEED_MORE_DATA",
    }
    assert payload["order_execution_allowed"] is False


def test_ticker_only_review_creates_linked_trade_review(client):
    created = client.post(
        "/api/ticker-reviews",
        json={
            "ticker": "TESTA",
            "review_mode": "momentum_review",
            "timeframe": "1d",
        },
    )
    assert created.status_code == 201
    body = created.json()
    review_id = body["ticker_review"]["trade_review_id"]

    listed = client.get("/api/trade-reviews")

    assert listed.status_code == 200
    reviews = listed.json()
    assert any(review["id"] == review_id for review in reviews)
    assert body["ticker_review"]["linked_meeting_id"] == body["trade_review"]["linked_meeting_id"]
    assert body["ticker_review"]["order_execution_allowed"] is False
    assert body["trade_review"]["order_execution_allowed"] is False


def test_ticker_review_order_execution_allowed_always_false(client):
    response = client.post(
        "/api/ticker-reviews",
        json={"ticker": "TESTB", "review_mode": "penny_stock_risk"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["order_execution_allowed"] is False
    assert payload["ticker_review"]["order_execution_allowed"] is False
    assert payload["trade_review"]["order_execution_allowed"] is False
    assert payload["structured_decision"]["order_execution_allowed"] is False


def test_mock_market_data_provider_for_test_ticker():
    provider = MockMarketDataProvider()

    snapshot = provider.fetch("TESTA", "penny_stock_risk", "1d")

    assert snapshot["provider"] == "mock_market_data"
    assert snapshot["ticker"] == "TESTA"
    assert snapshot["last_price"] == 0.82
    assert snapshot["volume"] == 12_500_000
    assert snapshot["market_data_available"] is True
    assert snapshot["news_available"] is True
    assert snapshot["data_quality"] == "sufficient"


def test_review_mode_payload_generation():
    market_data = MockMarketDataProvider().fetch("TESTA", "penny_stock_risk", "1d")
    for mode in [
        "penny_stock_risk",
        "momentum_review",
        "long_term_review",
        "news_catalyst_review",
        "general_review",
    ]:
        payload = build_auto_research_payload(
            payload=TickerReviewCreate(ticker="TESTA", review_mode=mode),
            market_data=market_data,
            provider_name="mock_market_data",
        )

        assert payload["ticker"] == "TESTA"
        assert payload["strategy_signal"] == "auto_research"
        assert payload["side"] == "review_only"
        assert payload["risk_context"]["review_mode"] == mode
        assert payload["risk_context"]["market_data_provider"] == "mock_market_data"
        assert payload["order_execution_allowed"] is False


def test_missing_market_data_marks_data_quality_limited(client):
    response = client.post(
        "/api/ticker-reviews",
        json={"ticker": "ABCD", "review_mode": "general_review"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["market_data"]["market_data_available"] is False
    assert payload["market_data"]["data_quality"] == "limited"
    assert payload["trade_review"]["input_payload"]["risk_context"]["data_quality"] == "limited"
    assert payload["structured_decision"]["data_quality"] == "limited"


def test_ticker_review_report_includes_auto_research_sections(client):
    created = client.post(
        "/api/ticker-reviews",
        json={
            "ticker": "TESTA",
            "review_mode": "penny_stock_risk",
            "notes": "종목만 입력한 자동 리서치 요청",
        },
    )
    assert created.status_code == 201
    meeting_id = created.json()["ticker_review"]["linked_meeting_id"]

    report = client.get(f"/api/meetings/{meeting_id}/report")

    assert report.status_code == 200
    assert "## 종목 자동 분석 요청" in report.text
    assert "## 자동 생성된 분석 payload" in report.text
    assert "## 사용된 데이터 provider" in report.text
    assert "## 데이터 품질" in report.text
    assert "## 안전 경계 (Safety Boundary)" in report.text


def test_ticker_review_code_does_not_add_broker_or_order_execution():
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
