from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.llm.config import LLMConfig
from app.main import create_app
from app.market_data import MarketDataConfig, MarketDataProviderError
from app.services.telegram_service import TelegramConfig
from app.webhooks import WebhookConfig


def test_market_data_status_api(client):
    response = client.get("/api/market-data/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock_market_data"
    assert payload["enabled"] is True
    assert payload["external_enabled"] is False
    assert payload["active_provider"] == "mock_market_data"
    assert payload["api_key_configured"] is False
    assert payload["last_check_status"] == "ok"
    assert payload["order_execution_allowed"] is False
    assert "mock_market_data" in payload["available_providers"]
    assert "polygon_stub" in payload["available_providers"]
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in payload["safety_boundary"]


def test_market_data_status_does_not_expose_secret_values(tmp_path):
    app = create_app(
        db_path=tmp_path / "ai_council.sqlite",
        report_dir=tmp_path / "reports",
        upload_root=tmp_path / "uploads",
        llm_config=LLMConfig(provider="mock"),
        telegram_config=TelegramConfig(enabled=False),
        webhook_config=WebhookConfig(enabled=False),
        market_data_config=MarketDataConfig(
            provider="polygon_stub",
            enabled=True,
            allow_external=True,
            polygon_api_key="secret-polygon-key",
        ),
    )
    with TestClient(app) as client:
        response = client.get("/api/market-data/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_key_configured"] is True
    assert "secret-polygon-key" not in response.text


def test_market_data_quote_api(client):
    response = client.get("/api/market-data/quote/TESTA")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "TESTA"
    assert payload["last_price"] == 0.82
    assert payload["bid"] is not None
    assert payload["ask"] is not None
    assert payload["spread_pct"] == 2.2
    assert payload["volume"] == 12_500_000
    assert payload["provider"] == "mock_market_data"
    assert payload["data_quality"] == "sufficient"
    assert payload["order_execution_allowed"] is False


def test_market_data_snapshot_api(client):
    response = client.get("/api/market-data/snapshot/TESTB")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "TESTB"
    assert payload["quote"]["ticker"] == "TESTB"
    assert payload["relative_volume"] == 7.4
    assert payload["premarket"] is True
    assert payload["risk_context"]["market_data_provider"] == "mock_market_data"
    assert payload["provider"] == "mock_market_data"
    assert payload["order_execution_allowed"] is False


def test_market_data_news_api(client):
    response = client.get("/api/market-data/news/TESTA")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "TESTA"
    assert payload["headlines"]
    assert payload["provider"] == "news_provider_stub"
    assert payload["order_execution_allowed"] is False


def test_market_data_filings_api(client):
    response = client.get("/api/market-data/filings/TESTA")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "TESTA"
    assert payload["filings"]
    assert payload["provider"] == "sec_filing_provider_stub"
    assert payload["order_execution_allowed"] is False


def test_ticker_review_uses_provider_snapshot(client):
    response = client.post(
        "/api/ticker-reviews",
        json={"ticker": "TESTD", "review_mode": "momentum_review", "timeframe": "1d"},
    )

    assert response.status_code == 201
    payload = response.json()
    risk_context = payload["trade_review"]["input_payload"]["risk_context"]
    assert payload["market_data"]["provider"] == "mock_market_data"
    assert payload["market_data"]["quote"]["ticker"] == "TESTD"
    assert risk_context["market_data_provider"] == "mock_market_data"
    assert risk_context["data_quality"] == payload["market_data"]["data_quality"]
    assert payload["order_execution_allowed"] is False


def test_provider_failure_fallback(monkeypatch, client):
    class FailingProvider:
        name = "failing_provider"

        def snapshot(self, ticker: str, review_mode: str = "penny_stock_risk", timeframe: str = "1d"):
            raise MarketDataProviderError("provider unavailable")

    monkeypatch.setattr(
        "app.ticker_reviews.get_market_data_provider",
        lambda config: FailingProvider(),
    )

    response = client.post(
        "/api/ticker-reviews",
        json={"ticker": "FAIL", "review_mode": "general_review"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["market_data"]["data_quality"] == "limited"
    assert payload["market_data"]["risk_context"]["provider_failure_fallback"] is True
    assert payload["structured_decision"]["order_execution_allowed"] is False


def test_market_data_code_does_not_add_broker_or_order_execution():
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
