from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Mapping

from .council import KOREAN_SAFETY_BOUNDARY


AVAILABLE_MARKET_DATA_PROVIDERS = [
    "mock_market_data",
    "external_market_data_stub",
    "polygon_stub",
    "alpaca_data_stub",
    "yahoo_finance_stub",
    "news_provider_stub",
    "sec_filing_provider_stub",
]


@dataclass(frozen=True)
class MarketDataConfig:
    provider: str = "mock_market_data"
    enabled: bool = False
    timeout_seconds: float = 10.0
    allow_external: bool = False
    polygon_api_key: str | None = None
    alpaca_data_api_key: str | None = None
    alpaca_data_api_secret: str | None = None
    news_provider_api_key: str | None = None
    sec_provider_enabled: bool = False

    @property
    def normalized_provider(self) -> str:
        provider = self.provider.strip().lower() or "mock_market_data"
        if provider == "mock":
            return "mock_market_data"
        return provider


def load_market_data_config(environ: Mapping[str, str] | None = None) -> MarketDataConfig:
    values = os.environ if environ is None else environ
    timeout_raw = values.get("MARKET_DATA_TIMEOUT_SECONDS", "10")
    try:
        timeout_seconds = float(timeout_raw)
    except ValueError:
        timeout_seconds = 10.0
    return MarketDataConfig(
        provider=(values.get("MARKET_DATA_PROVIDER", "mock_market_data").strip() or "mock_market_data"),
        enabled=_as_bool(values.get("MARKET_DATA_ENABLED", "false")),
        timeout_seconds=timeout_seconds,
        allow_external=_as_bool(values.get("MARKET_DATA_ALLOW_EXTERNAL", "false")),
        polygon_api_key=(values.get("POLYGON_API_KEY") or "").strip() or None,
        alpaca_data_api_key=(values.get("ALPACA_DATA_API_KEY") or "").strip() or None,
        alpaca_data_api_secret=(values.get("ALPACA_DATA_API_SECRET") or "").strip() or None,
        news_provider_api_key=(values.get("NEWS_PROVIDER_API_KEY") or "").strip() or None,
        sec_provider_enabled=_as_bool(values.get("SEC_PROVIDER_ENABLED", "false")),
    )


class MarketDataProviderError(Exception):
    pass


class MarketDataProvider:
    name = "market_data_provider"

    def status(self, config: MarketDataConfig) -> dict:
        return market_data_status(config, active_provider=self.name)

    def quote(self, ticker: str) -> dict:
        raise NotImplementedError

    def snapshot(self, ticker: str, review_mode: str = "penny_stock_risk", timeframe: str = "1d") -> dict:
        raise NotImplementedError

    def news(self, ticker: str) -> dict:
        raise NotImplementedError

    def filings(self, ticker: str) -> dict:
        raise NotImplementedError

    def scan_candidates(self, universe: str, review_mode: str, max_candidates: int, timeframe: str) -> list[dict]:
        raise NotImplementedError

    def fetch(self, ticker: str, review_mode: str, timeframe: str) -> dict:
        return self.snapshot(ticker, review_mode=review_mode, timeframe=timeframe)


class MockMarketDataProvider(MarketDataProvider):
    name = "mock_market_data"

    def quote(self, ticker: str) -> dict:
        normalized_ticker = _normalize_ticker(ticker)
        data = _mock_base_snapshot(normalized_ticker)
        last_price = data["last_price"]
        spread_pct = data["spread_pct"]
        if last_price is None or spread_pct is None:
            bid = None
            ask = None
        else:
            spread_value = last_price * (spread_pct / 100)
            bid = round(last_price - (spread_value / 2), 4)
            ask = round(last_price + (spread_value / 2), 4)
        return {
            "ticker": normalized_ticker,
            "last_price": last_price,
            "bid": bid,
            "ask": ask,
            "spread_pct": spread_pct,
            "volume": data["volume"],
            "timestamp": _now_iso(),
            "provider": self.name,
            "data_quality": data["data_quality"],
            "order_execution_allowed": False,
        }

    def snapshot(self, ticker: str, review_mode: str = "penny_stock_risk", timeframe: str = "1d") -> dict:
        normalized_ticker = _normalize_ticker(ticker)
        data = _mock_base_snapshot(normalized_ticker)
        quote = self.quote(normalized_ticker)
        return {
            "provider": self.name,
            "ticker": normalized_ticker,
            "quote": quote,
            "last_price": quote["last_price"],
            "volume": quote["volume"],
            "relative_volume": data["relative_volume"],
            "spread_pct": quote["spread_pct"],
            "premarket": data["premarket"],
            "mock_news_headlines": data["mock_news_headlines"],
            "market_data_available": data["market_data_available"],
            "news_available": bool(data["mock_news_headlines"]),
            "risk_context": {
                "review_mode": review_mode,
                "timeframe": timeframe,
                "market_data_provider": self.name,
                "market_data_available": data["market_data_available"],
                "news_available": bool(data["mock_news_headlines"]),
                "data_quality": data["data_quality"],
                "spread_pct": quote["spread_pct"],
                "premarket": data["premarket"],
                "relative_volume": data["relative_volume"],
            },
            "data_quality": data["data_quality"],
            "notes": data["notes"],
            "order_execution_allowed": False,
        }

    def news(self, ticker: str) -> dict:
        normalized_ticker = _normalize_ticker(ticker)
        data = _mock_base_snapshot(normalized_ticker)
        return {
            "ticker": normalized_ticker,
            "headlines": data["mock_news_headlines"],
            "provider": "news_provider_stub",
            "data_quality": "sufficient" if data["mock_news_headlines"] else "limited",
            "fetched_at": _now_iso(),
            "order_execution_allowed": False,
        }

    def filings(self, ticker: str) -> dict:
        normalized_ticker = _normalize_ticker(ticker)
        filings = (
            [
                {
                    "form": "8-K",
                    "filed_at": "2026-06-01",
                    "description": f"Mock filing placeholder for {normalized_ticker}",
                }
            ]
            if normalized_ticker.startswith("TEST")
            else []
        )
        return {
            "ticker": normalized_ticker,
            "filings": filings,
            "provider": "sec_filing_provider_stub",
            "data_quality": "limited",
            "fetched_at": _now_iso(),
            "order_execution_allowed": False,
        }

    def scan_candidates(self, universe: str, review_mode: str, max_candidates: int, timeframe: str) -> list[dict]:
        candidates = _candidate_universe(universe)
        normalized = []
        for candidate in candidates[:max_candidates]:
            snapshot = self.snapshot(
                candidate["ticker"],
                review_mode=review_mode,
                timeframe=timeframe,
            )
            snapshot.update(
                {
                    "last_price": candidate["last_price"],
                    "volume": candidate["volume"],
                    "relative_volume": candidate["relative_volume"],
                    "spread_pct": candidate["spread_pct"],
                    "premarket": candidate["premarket"],
                    "mock_news_headlines": candidate["mock_news_headlines"],
                    "market_data_available": candidate["market_data_available"],
                    "news_available": bool(candidate["mock_news_headlines"]),
                    "data_quality": candidate["data_quality"],
                    "scan_reason": candidate["scan_reason"],
                    "risk_context": {
                        **snapshot.get("risk_context", {}),
                        "universe": universe,
                        "scan_reason": candidate["scan_reason"],
                        "autonomous_review": True,
                    },
                    "notes": f"Mock autonomous candidate generated for {universe}.",
                    "order_execution_allowed": False,
                }
            )
            normalized.append(snapshot)
        return normalized


class StubMarketDataProvider(MarketDataProvider):
    def __init__(self, name: str):
        self.name = name

    def quote(self, ticker: str) -> dict:
        normalized_ticker = _normalize_ticker(ticker)
        return {
            "ticker": normalized_ticker,
            "last_price": None,
            "bid": None,
            "ask": None,
            "spread_pct": None,
            "volume": None,
            "timestamp": _now_iso(),
            "provider": self.name,
            "data_quality": "limited",
            "order_execution_allowed": False,
            "stub": True,
            "detail": f"{self.name} is disabled and does not call external APIs in Phase 12.",
        }

    def snapshot(self, ticker: str, review_mode: str = "penny_stock_risk", timeframe: str = "1d") -> dict:
        quote = self.quote(ticker)
        return {
            "provider": self.name,
            "ticker": quote["ticker"],
            "quote": quote,
            "last_price": None,
            "volume": None,
            "relative_volume": None,
            "spread_pct": None,
            "premarket": False,
            "mock_news_headlines": [],
            "market_data_available": False,
            "news_available": False,
            "risk_context": {
                "review_mode": review_mode,
                "timeframe": timeframe,
                "market_data_provider": self.name,
                "market_data_available": False,
                "news_available": False,
                "data_quality": "limited",
            },
            "data_quality": "limited",
            "notes": f"{self.name} is a future extension stub and does not call external APIs.",
            "order_execution_allowed": False,
        }

    def news(self, ticker: str) -> dict:
        return {
            "ticker": _normalize_ticker(ticker),
            "headlines": [],
            "provider": "news_provider_stub",
            "data_quality": "limited",
            "fetched_at": _now_iso(),
            "order_execution_allowed": False,
        }

    def filings(self, ticker: str) -> dict:
        return {
            "ticker": _normalize_ticker(ticker),
            "filings": [],
            "provider": "sec_filing_provider_stub",
            "data_quality": "limited",
            "fetched_at": _now_iso(),
            "order_execution_allowed": False,
        }

    def scan_candidates(self, universe: str, review_mode: str, max_candidates: int, timeframe: str) -> list[dict]:
        return MockMarketDataProvider().scan_candidates(universe, review_mode, max_candidates, timeframe)


def get_market_data_provider(config: MarketDataConfig) -> MarketDataProvider:
    provider = config.normalized_provider
    if provider == "mock_market_data":
        return MockMarketDataProvider()
    if provider in AVAILABLE_MARKET_DATA_PROVIDERS and config.allow_external:
        return StubMarketDataProvider(provider)
    return MockMarketDataProvider()


def market_data_status(config: MarketDataConfig, active_provider: str | None = None) -> dict:
    provider = config.normalized_provider
    active = active_provider or get_market_data_provider(config).name
    return {
        "provider": provider,
        "enabled": True,
        "external_enabled": bool(config.allow_external and config.enabled),
        "available_providers": AVAILABLE_MARKET_DATA_PROVIDERS,
        "active_provider": active,
        "api_key_configured": _api_key_configured(config, provider),
        "last_check_status": "ok" if active == "mock_market_data" else "stub",
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def safe_fallback_snapshot(ticker: str, provider_name: str = "market_data_fallback") -> dict:
    normalized_ticker = _normalize_ticker(ticker)
    return {
        "provider": provider_name,
        "ticker": normalized_ticker,
        "quote": {
            "ticker": normalized_ticker,
            "last_price": None,
            "bid": None,
            "ask": None,
            "spread_pct": None,
            "volume": None,
            "timestamp": _now_iso(),
            "provider": provider_name,
            "data_quality": "limited",
            "order_execution_allowed": False,
        },
        "last_price": None,
        "volume": None,
        "relative_volume": None,
        "spread_pct": None,
        "premarket": False,
        "mock_news_headlines": [],
        "market_data_available": False,
        "news_available": False,
        "risk_context": {
            "market_data_provider": provider_name,
            "market_data_available": False,
            "news_available": False,
            "data_quality": "limited",
            "provider_failure_fallback": True,
        },
        "data_quality": "limited",
        "notes": "Market data provider failed or was unavailable; using limited fallback context.",
        "order_execution_allowed": False,
    }


def _mock_base_snapshot(ticker: str) -> dict:
    candidates = {candidate["ticker"]: candidate for candidate in _candidate_universe("mock_penny_stocks")}
    if ticker in candidates:
        candidate = candidates[ticker]
        return {
            **candidate,
            "news_available": bool(candidate["mock_news_headlines"]),
            "notes": "Mock TEST ticker data for safe local review.",
        }
    return {
        "ticker": ticker,
        "last_price": None,
        "volume": None,
        "relative_volume": None,
        "spread_pct": None,
        "premarket": False,
        "mock_news_headlines": [],
        "market_data_available": False,
        "news_available": False,
        "data_quality": "limited",
        "scan_reason": "market_data_unavailable",
        "notes": "Mock provider has no market data for this ticker.",
    }


def _candidate_universe(universe: str) -> list[dict]:
    base = [
        {
            "ticker": "TESTA",
            "last_price": 0.82,
            "volume": 12_500_000,
            "relative_volume": 4.8,
            "spread_pct": 2.2,
            "premarket": False,
            "mock_news_headlines": ["TESTA sample catalyst requires validation"],
            "market_data_available": True,
            "data_quality": "sufficient",
            "scan_reason": "relative_volume_spike",
        },
        {
            "ticker": "TESTB",
            "last_price": 0.47,
            "volume": 850_000,
            "relative_volume": 7.4,
            "spread_pct": 8.4,
            "premarket": True,
            "mock_news_headlines": ["TESTB sample premarket attention increases"],
            "market_data_available": True,
            "data_quality": "limited",
            "scan_reason": "high_spread_risk",
        },
        {
            "ticker": "TESTC",
            "last_price": 1.14,
            "volume": 2_400_000,
            "relative_volume": 3.1,
            "spread_pct": 2.9,
            "premarket": False,
            "mock_news_headlines": [],
            "market_data_available": True,
            "data_quality": "limited",
            "scan_reason": "insufficient_news",
        },
        {
            "ticker": "TESTD",
            "last_price": 2.08,
            "volume": 4_900_000,
            "relative_volume": 5.9,
            "spread_pct": 1.4,
            "premarket": False,
            "mock_news_headlines": ["TESTD mock product update"],
            "market_data_available": True,
            "data_quality": "sufficient",
            "scan_reason": "price_momentum",
        },
        {
            "ticker": "TESTE",
            "last_price": 0.31,
            "volume": 1_200_000,
            "relative_volume": 6.6,
            "spread_pct": 4.1,
            "premarket": True,
            "mock_news_headlines": ["TESTE mock catalyst watch"],
            "market_data_available": True,
            "data_quality": "limited",
            "scan_reason": "news_catalyst",
        },
    ]
    if universe == "mock_momentum_stocks":
        return [base[3], base[0], base[4], base[2], base[1]]
    if universe == "mock_watchlist":
        return [base[0], base[2], base[3]]
    if universe == "custom_stub":
        return [
            {
                **base[0],
                "ticker": "TESTX",
                "scan_reason": "custom_stub",
                "mock_news_headlines": [],
                "data_quality": "limited",
            }
        ]
    return base


def _api_key_configured(config: MarketDataConfig, provider: str) -> bool:
    if provider == "polygon_stub":
        return bool(config.polygon_api_key)
    if provider == "alpaca_data_stub":
        return bool(config.alpaca_data_api_key and config.alpaca_data_api_secret)
    if provider == "news_provider_stub":
        return bool(config.news_provider_api_key)
    if provider == "sec_filing_provider_stub":
        return bool(config.sec_provider_enabled)
    return False


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _as_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
