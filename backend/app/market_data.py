from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MarketDataConfig:
    provider: str = "mock"
    timeout_seconds: float = 10.0


def load_market_data_config() -> MarketDataConfig:
    timeout_raw = os.getenv("MARKET_DATA_TIMEOUT_SECONDS", "10")
    try:
        timeout_seconds = float(timeout_raw)
    except ValueError:
        timeout_seconds = 10.0
    return MarketDataConfig(
        provider=os.getenv("MARKET_DATA_PROVIDER", "mock").strip() or "mock",
        timeout_seconds=timeout_seconds,
    )


class MarketDataProvider:
    name = "market_data_provider"

    def fetch(self, ticker: str, review_mode: str, timeframe: str) -> dict:
        raise NotImplementedError


class MockMarketDataProvider(MarketDataProvider):
    name = "mock_market_data"

    def fetch(self, ticker: str, review_mode: str, timeframe: str) -> dict:
        normalized_ticker = ticker.strip().upper()
        if review_mode == "penny_stock_risk" and normalized_ticker.startswith("TEST"):
            return {
                "provider": self.name,
                "ticker": normalized_ticker,
                "last_price": 0.82,
                "volume": 12_500_000,
                "relative_volume": 4.8,
                "spread_pct": 2.2,
                "premarket": False,
                "mock_news_headlines": [
                    f"{normalized_ticker} sample catalyst requires validation",
                    f"{normalized_ticker} mock filing review remains pending",
                ],
                "market_data_available": True,
                "news_available": True,
                "data_quality": "sufficient",
                "notes": "Mock TEST ticker data for safe local review.",
            }
        return {
            "provider": self.name,
            "ticker": normalized_ticker,
            "last_price": None,
            "volume": None,
            "relative_volume": None,
            "spread_pct": None,
            "premarket": False,
            "mock_news_headlines": [],
            "market_data_available": False,
            "news_available": False,
            "data_quality": "limited",
            "notes": "Mock provider has no market data for this ticker.",
        }


class ExternalMarketDataStubProvider(MarketDataProvider):
    name = "external_market_data_stub"

    def fetch(self, ticker: str, review_mode: str, timeframe: str) -> dict:
        return _stub_snapshot(self.name, ticker)


class NewsProviderStub(MarketDataProvider):
    name = "news_provider_stub"

    def fetch(self, ticker: str, review_mode: str, timeframe: str) -> dict:
        return _stub_snapshot(self.name, ticker)


class SecFilingProviderStub(MarketDataProvider):
    name = "sec_filing_provider_stub"

    def fetch(self, ticker: str, review_mode: str, timeframe: str) -> dict:
        return _stub_snapshot(self.name, ticker)


def _stub_snapshot(provider_name: str, ticker: str) -> dict:
    return {
        "provider": provider_name,
        "ticker": ticker.strip().upper(),
        "last_price": None,
        "volume": None,
        "relative_volume": None,
        "spread_pct": None,
        "premarket": False,
        "mock_news_headlines": [],
        "market_data_available": False,
        "news_available": False,
        "data_quality": "limited",
        "notes": f"{provider_name} is a future extension stub and does not call external APIs.",
    }


def get_market_data_provider(config: MarketDataConfig) -> MarketDataProvider:
    provider = config.provider.strip().lower()
    if provider in {"mock", "mock_market_data"}:
        return MockMarketDataProvider()
    if provider == "external_market_data_stub":
        return ExternalMarketDataStubProvider()
    if provider == "news_provider_stub":
        return NewsProviderStub()
    if provider == "sec_filing_provider_stub":
        return SecFilingProviderStub()
    return MockMarketDataProvider()
