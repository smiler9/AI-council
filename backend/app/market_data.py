from __future__ import annotations

import importlib
import importlib.util
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from .council import KOREAN_SAFETY_BOUNDARY


AVAILABLE_MARKET_DATA_PROVIDERS = [
    "mock_market_data",
    "external_market_data_stub",
    "polygon_stub",
    "alpaca_data_stub",
    "yahoo_finance",
    "yahoo_finance_stub",
    "news_provider_stub",
    "sec_filing_provider_stub",
]


@dataclass(frozen=True)
class MarketDataConfig:
    provider: str = "mock_market_data"
    enabled: bool = True
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
        enabled=_as_bool(values.get("MARKET_DATA_ENABLED", "true")),
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


class YahooFinanceMarketDataProvider(MarketDataProvider):
    name = "yahoo_finance"

    def __init__(self, config: MarketDataConfig):
        self.config = config

    def quote(self, ticker: str) -> dict:
        normalized_ticker = _normalize_ticker(ticker)
        warning = self._provider_warning()
        if warning:
            return self._fallback_quote(normalized_ticker, warning)

        try:
            ticker_obj = self._ticker(normalized_ticker)
            fast_info = getattr(ticker_obj, "fast_info", None)
            info = getattr(ticker_obj, "info", None)
            last_price = _first_number(
                [fast_info, info],
                [
                    "last_price",
                    "lastPrice",
                    "regular_market_price",
                    "regularMarketPrice",
                    "currentPrice",
                    "previousClose",
                ],
            )
            bid = _first_number([fast_info, info], ["bid", "bidPrice"])
            ask = _first_number([fast_info, info], ["ask", "askPrice"])
            volume = _first_int(
                [fast_info, info],
                [
                    "last_volume",
                    "lastVolume",
                    "regular_market_volume",
                    "regularMarketVolume",
                    "volume",
                ],
            )
            spread_pct = _spread_pct(bid, ask)
            data_quality = "sufficient" if last_price is not None and volume is not None else "limited"
            provider_warning = None
            if data_quality != "sufficient":
                provider_warning = "Yahoo Finance quote is missing price or volume fields."
            return {
                "ticker": normalized_ticker,
                "last_price": last_price,
                "bid": bid,
                "ask": ask,
                "spread_pct": spread_pct,
                "volume": volume,
                "timestamp": _now_iso(),
                "provider": self.name,
                "data_quality": data_quality,
                "provider_warning": provider_warning,
                "external_data": True,
                "order_execution_allowed": False,
            }
        except Exception as exc:
            return self._fallback_quote(
                normalized_ticker,
                f"Yahoo Finance quote lookup failed: {exc}",
            )

    def snapshot(self, ticker: str, review_mode: str = "penny_stock_risk", timeframe: str = "1d") -> dict:
        normalized_ticker = _normalize_ticker(ticker)
        quote = self.quote(normalized_ticker)
        headlines = []
        headline_warning = None
        if quote.get("external_data"):
            try:
                headlines = _normalize_news_headlines(getattr(self._ticker(normalized_ticker), "news", []) or [])
            except Exception as exc:
                headline_warning = f"Yahoo Finance headline lookup failed: {exc}"

        data_quality = quote.get("data_quality") or "limited"
        market_data_available = quote.get("last_price") is not None or quote.get("volume") is not None
        if not market_data_available:
            data_quality = "unavailable"
        elif not headlines:
            data_quality = "limited" if data_quality == "sufficient" else data_quality

        provider_warning = quote.get("provider_warning") or headline_warning
        return {
            "provider": self.name,
            "ticker": normalized_ticker,
            "quote": quote,
            "last_price": quote.get("last_price"),
            "volume": quote.get("volume"),
            "relative_volume": None,
            "spread_pct": quote.get("spread_pct"),
            "premarket": False,
            "mock_news_headlines": headlines,
            "market_data_available": market_data_available,
            "news_available": bool(headlines),
            "risk_context": {
                "review_mode": review_mode,
                "timeframe": timeframe,
                "market_data_provider": self.name,
                "market_data_available": market_data_available,
                "news_available": bool(headlines),
                "data_quality": data_quality,
                "spread_pct": quote.get("spread_pct"),
                "premarket": False,
                "relative_volume": None,
                "external_data": bool(quote.get("external_data")),
                "provider_warning": provider_warning,
            },
            "data_quality": data_quality,
            "provider_warning": provider_warning,
            "notes": "Yahoo Finance read-only market data. Values may be delayed, missing, or incomplete.",
            "order_execution_allowed": False,
        }

    def news(self, ticker: str) -> dict:
        return {
            "ticker": _normalize_ticker(ticker),
            "headlines": [],
            "provider": "news_provider_stub",
            "data_quality": "limited",
            "fetched_at": _now_iso(),
            "provider_warning": "Dedicated Yahoo/news provider endpoint is not implemented in Phase 13.",
            "order_execution_allowed": False,
        }

    def filings(self, ticker: str) -> dict:
        return {
            "ticker": _normalize_ticker(ticker),
            "filings": [],
            "provider": "sec_filing_provider_stub",
            "data_quality": "limited",
            "fetched_at": _now_iso(),
            "provider_warning": "SEC filing provider is a stub in Phase 13 and does not call SEC APIs.",
            "order_execution_allowed": False,
        }

    def scan_candidates(self, universe: str, review_mode: str, max_candidates: int, timeframe: str) -> list[dict]:
        mock_candidates = MockMarketDataProvider().scan_candidates(
            universe=universe,
            review_mode=review_mode,
            max_candidates=max_candidates,
            timeframe=timeframe,
        )
        if self._provider_warning():
            return mock_candidates

        enriched = []
        for candidate in mock_candidates:
            try:
                snapshot = self.snapshot(
                    candidate["ticker"],
                    review_mode=review_mode,
                    timeframe=timeframe,
                )
            except Exception:
                enriched.append(candidate)
                continue
            if not snapshot.get("market_data_available"):
                enriched.append(candidate)
                continue
            snapshot.update(
                {
                    "scan_reason": candidate["scan_reason"],
                    "risk_context": {
                        **snapshot.get("risk_context", {}),
                        "universe": universe,
                        "scan_reason": candidate["scan_reason"],
                        "autonomous_review": True,
                    },
                    "order_execution_allowed": False,
                }
            )
            enriched.append(snapshot)
        return enriched

    def _ticker(self, ticker: str):
        yfinance = _load_yfinance()
        if yfinance is None:
            raise MarketDataProviderError("yfinance is not installed")
        return yfinance.Ticker(ticker)

    def _provider_warning(self) -> str | None:
        if not self.config.enabled:
            return "MARKET_DATA_ENABLED=false; Yahoo Finance external lookup is disabled."
        if not self.config.allow_external:
            return "MARKET_DATA_ALLOW_EXTERNAL=false; Yahoo Finance external lookup is disabled."
        if not _yfinance_installed():
            return "yfinance is not installed; Yahoo Finance provider is unavailable."
        return None

    def _fallback_quote(self, ticker: str, warning: str) -> dict:
        return {
            "ticker": ticker,
            "last_price": None,
            "bid": None,
            "ask": None,
            "spread_pct": None,
            "volume": None,
            "timestamp": _now_iso(),
            "provider": self.name,
            "data_quality": "unavailable",
            "provider_warning": warning,
            "external_data": False,
            "order_execution_allowed": False,
        }


def get_market_data_provider(config: MarketDataConfig) -> MarketDataProvider:
    provider = config.normalized_provider
    if provider == "mock_market_data":
        return MockMarketDataProvider()
    if provider == "yahoo_finance":
        return YahooFinanceMarketDataProvider(config)
    if provider in AVAILABLE_MARKET_DATA_PROVIDERS and config.allow_external:
        return StubMarketDataProvider(provider)
    return MockMarketDataProvider()


def market_data_status(config: MarketDataConfig, active_provider: str | None = None) -> dict:
    provider = config.normalized_provider
    active = active_provider or get_market_data_provider(config).name
    external_calls_allowed = bool(config.enabled and config.allow_external)
    yfinance_installed = _yfinance_installed()
    yahoo_finance_available = bool(external_calls_allowed and yfinance_installed)
    provider_warning = _provider_status_warning(provider, active, config, yfinance_installed)
    if provider == "yahoo_finance" and provider_warning:
        last_check_status = "disabled" if not external_calls_allowed else "unavailable"
    elif active == "mock_market_data":
        last_check_status = "ok"
    elif active == "yahoo_finance":
        last_check_status = "ok" if yahoo_finance_available else "unavailable"
    else:
        last_check_status = "stub"
    return {
        "provider": provider,
        "enabled": True if provider == "mock_market_data" else bool(config.enabled),
        "external_enabled": external_calls_allowed,
        "available_providers": AVAILABLE_MARKET_DATA_PROVIDERS,
        "active_provider": active,
        "api_key_configured": _api_key_configured(config, provider),
        "yahoo_finance_available": yahoo_finance_available,
        "yfinance_installed": yfinance_installed,
        "external_calls_allowed": external_calls_allowed,
        "last_check_status": last_check_status,
        "provider_warning": provider_warning,
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


def _provider_status_warning(
    provider: str,
    active: str,
    config: MarketDataConfig,
    yfinance_installed: bool,
) -> str | None:
    if provider == "yahoo_finance":
        if not config.enabled:
            return "MARKET_DATA_ENABLED=false; Yahoo Finance provider is disabled."
        if not config.allow_external:
            return "MARKET_DATA_ALLOW_EXTERNAL=false; Yahoo Finance external calls are blocked."
        if not yfinance_installed:
            return "yfinance is not installed; Yahoo Finance provider is unavailable."
        return "Yahoo Finance data may be delayed, missing, or incomplete."
    if active not in {"mock_market_data", "yahoo_finance"}:
        return f"{active} is a Phase 13 stub and does not call external APIs."
    return None


def _yfinance_installed() -> bool:
    try:
        return importlib.util.find_spec("yfinance") is not None
    except (ImportError, ValueError):
        return False


def _load_yfinance():
    if not _yfinance_installed():
        return None
    try:
        return importlib.import_module("yfinance")
    except Exception:
        return None


def _first_number(sources: list[Any], keys: list[str]) -> float | None:
    value = _first_value(sources, keys)
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _first_int(sources: list[Any], keys: list[str]) -> int | None:
    value = _first_number(sources, keys)
    if value is None:
        return None
    return int(value)


def _first_value(sources: list[Any], keys: list[str]) -> Any:
    for source in sources:
        if source is None:
            continue
        for key in keys:
            value = _lookup_value(source, key)
            if value is not None and value != "":
                return value
    return None


def _lookup_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    try:
        return source[key]
    except Exception:
        return getattr(source, key, None)


def _spread_pct(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None:
        return None
    midpoint = (bid + ask) / 2
    if midpoint <= 0:
        return None
    return round(((ask - bid) / midpoint) * 100, 4)


def _normalize_news_headlines(news_items: list[Any]) -> list[str]:
    headlines = []
    for item in news_items[:5]:
        title = _lookup_value(item, "title") or _lookup_value(item, "headline")
        if title:
            headlines.append(str(title))
    return headlines


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _as_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
