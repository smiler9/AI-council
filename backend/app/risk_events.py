from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Mapping

from .council import KOREAN_SAFETY_BOUNDARY


AVAILABLE_NEWS_PROVIDERS = [
    "mock_news_provider",
    "external_news_stub",
    "finnhub_news_stub",
    "polygon_news_stub",
]
AVAILABLE_SEC_FILING_PROVIDERS = [
    "mock_sec_filing_provider",
    "sec_edgar_stub",
]
AVAILABLE_RISK_EVENT_PROVIDERS = [
    "risk_event_detector",
]

HIGH_IMPACT_EVENTS = {
    "offering",
    "reverse_split",
    "delisting_notice",
    "trading_halt",
    "pump_promotion",
    "bankruptcy_risk",
    "dilution_risk",
    "sec_investigation",
}


@dataclass(frozen=True)
class RiskEventConfig:
    news_provider: str = "mock_news_provider"
    news_enabled: bool = True
    news_allow_external: bool = False
    news_timeout_seconds: float = 10.0
    sec_filing_provider: str = "mock_sec_filing_provider"
    sec_filing_enabled: bool = True
    sec_allow_external: bool = False
    sec_timeout_seconds: float = 10.0
    detector_enabled: bool = True
    finnhub_api_key: str | None = None
    polygon_api_key: str | None = None

    @property
    def normalized_news_provider(self) -> str:
        return self.news_provider.strip().lower() or "mock_news_provider"

    @property
    def normalized_sec_filing_provider(self) -> str:
        return self.sec_filing_provider.strip().lower() or "mock_sec_filing_provider"


def load_risk_event_config(environ: Mapping[str, str] | None = None) -> RiskEventConfig:
    values = os.environ if environ is None else environ
    return RiskEventConfig(
        news_provider=(values.get("NEWS_PROVIDER", "mock_news_provider").strip() or "mock_news_provider"),
        news_enabled=_as_bool(values.get("NEWS_PROVIDER_ENABLED", "true")),
        news_allow_external=_as_bool(values.get("NEWS_ALLOW_EXTERNAL", "false")),
        news_timeout_seconds=_as_float(values.get("NEWS_TIMEOUT_SECONDS"), 10.0),
        sec_filing_provider=(
            values.get("SEC_FILING_PROVIDER", "mock_sec_filing_provider").strip()
            or "mock_sec_filing_provider"
        ),
        sec_filing_enabled=_as_bool(values.get("SEC_FILING_ENABLED", "true")),
        sec_allow_external=_as_bool(values.get("SEC_ALLOW_EXTERNAL", "false")),
        sec_timeout_seconds=_as_float(values.get("SEC_TIMEOUT_SECONDS"), 10.0),
        detector_enabled=_as_bool(values.get("RISK_EVENT_DETECTOR_ENABLED", "true")),
        finnhub_api_key=(values.get("FINNHUB_API_KEY") or "").strip() or None,
        polygon_api_key=(values.get("POLYGON_API_KEY") or "").strip() or None,
    )


class NewsProvider:
    name = "news_provider"

    def news(self, ticker: str) -> dict:
        raise NotImplementedError


class SecFilingProvider:
    name = "sec_filing_provider"

    def filings(self, ticker: str) -> dict:
        raise NotImplementedError


class MockNewsProvider(NewsProvider):
    name = "mock_news_provider"

    def news(self, ticker: str) -> dict:
        normalized_ticker = _normalize_ticker(ticker)
        headlines = _mock_headlines(normalized_ticker)
        return {
            "ticker": normalized_ticker,
            "headlines": headlines,
            "provider": self.name,
            "data_quality": "mock" if headlines else "limited",
            "fetched_at": _now_iso(),
            "order_execution_allowed": False,
            "safety_boundary": KOREAN_SAFETY_BOUNDARY,
        }


class MockSecFilingProvider(SecFilingProvider):
    name = "mock_sec_filing_provider"

    def filings(self, ticker: str) -> dict:
        normalized_ticker = _normalize_ticker(ticker)
        filings = _mock_filings(normalized_ticker)
        return {
            "ticker": normalized_ticker,
            "filings": filings,
            "provider": self.name,
            "data_quality": "mock" if filings else "limited",
            "fetched_at": _now_iso(),
            "order_execution_allowed": False,
            "safety_boundary": KOREAN_SAFETY_BOUNDARY,
        }


class StubNewsProvider(NewsProvider):
    def __init__(self, name: str):
        self.name = name

    def news(self, ticker: str) -> dict:
        return {
            "ticker": _normalize_ticker(ticker),
            "headlines": [],
            "provider": self.name,
            "data_quality": "limited",
            "fetched_at": _now_iso(),
            "provider_warning": f"{self.name} is a Phase 14 stub and does not call external news APIs.",
            "order_execution_allowed": False,
            "safety_boundary": KOREAN_SAFETY_BOUNDARY,
        }


class StubSecFilingProvider(SecFilingProvider):
    def __init__(self, name: str):
        self.name = name

    def filings(self, ticker: str) -> dict:
        return {
            "ticker": _normalize_ticker(ticker),
            "filings": [],
            "provider": self.name,
            "data_quality": "limited",
            "fetched_at": _now_iso(),
            "provider_warning": f"{self.name} is a Phase 14 stub and does not call SEC APIs.",
            "order_execution_allowed": False,
            "safety_boundary": KOREAN_SAFETY_BOUNDARY,
        }


def get_news_provider(config: RiskEventConfig) -> NewsProvider:
    provider = config.normalized_news_provider
    if provider == "mock_news_provider":
        return MockNewsProvider()
    if provider in AVAILABLE_NEWS_PROVIDERS and config.news_enabled and config.news_allow_external:
        return StubNewsProvider(provider)
    return MockNewsProvider()


def get_sec_filing_provider(config: RiskEventConfig) -> SecFilingProvider:
    provider = config.normalized_sec_filing_provider
    if provider == "mock_sec_filing_provider":
        return MockSecFilingProvider()
    if provider in AVAILABLE_SEC_FILING_PROVIDERS and config.sec_filing_enabled and config.sec_allow_external:
        return StubSecFilingProvider(provider)
    return MockSecFilingProvider()


def risk_event_status(config: RiskEventConfig) -> dict:
    news_provider = get_news_provider(config).name
    sec_provider = get_sec_filing_provider(config).name
    return {
        "news_provider": config.normalized_news_provider,
        "sec_filing_provider": config.normalized_sec_filing_provider,
        "risk_event_detector": "risk_event_detector",
        "news_enabled": config.news_enabled,
        "sec_filing_enabled": config.sec_filing_enabled,
        "detector_enabled": config.detector_enabled,
        "news_external_enabled": bool(config.news_enabled and config.news_allow_external),
        "sec_external_enabled": bool(config.sec_filing_enabled and config.sec_allow_external),
        "active_news_provider": news_provider,
        "active_sec_filing_provider": sec_provider,
        "available_news_providers": AVAILABLE_NEWS_PROVIDERS,
        "available_sec_filing_providers": AVAILABLE_SEC_FILING_PROVIDERS,
        "available_risk_event_providers": AVAILABLE_RISK_EVENT_PROVIDERS,
        "finnhub_api_key_configured": bool(config.finnhub_api_key),
        "polygon_api_key_configured": bool(config.polygon_api_key),
        "last_check_status": "ok",
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def detect_risk_events(ticker: str, config: RiskEventConfig) -> dict:
    normalized_ticker = _normalize_ticker(ticker)
    if not config.detector_enabled:
        return _detection_response(
            ticker=normalized_ticker,
            news_response=get_news_provider(config).news(normalized_ticker),
            filing_response=get_sec_filing_provider(config).filings(normalized_ticker),
            events=[],
            data_quality="limited",
            provider_warning="Risk event detector is disabled.",
        )

    news_response = get_news_provider(config).news(normalized_ticker)
    filing_response = get_sec_filing_provider(config).filings(normalized_ticker)
    events = _detect_events_from_sources(news_response, filing_response)
    if not news_response.get("headlines"):
        events.append(
            _event(
                event_type="no_recent_news",
                severity="medium",
                confidence=0.78,
                evidence=["No recent mock news headline was available."],
                recommended_decision_impact="NEED_MORE_DATA",
            )
        )
    if not filing_response.get("filings"):
        events.append(
            _event(
                event_type="insufficient_disclosure",
                severity="medium",
                confidence=0.65,
                evidence=["No recent mock SEC filing was available."],
                recommended_decision_impact="NEED_MORE_DATA",
            )
        )
    data_quality = _combined_data_quality(news_response, filing_response, events)
    return _detection_response(
        ticker=normalized_ticker,
        news_response=news_response,
        filing_response=filing_response,
        events=events,
        data_quality=data_quality,
    )


def _detect_events_from_sources(news_response: dict, filing_response: dict) -> list[dict]:
    events: list[dict] = []
    news_texts = [
        str(item.get("title") or "")
        for item in news_response.get("headlines", [])
    ]
    filing_texts = [
        " ".join(
            [
                str(item.get("form") or ""),
                str(item.get("description") or ""),
                str(item.get("text") or ""),
            ]
        )
        for item in filing_response.get("filings", [])
    ]
    all_texts = news_texts + filing_texts
    lowered = " ".join(all_texts).lower()

    if _contains_any(lowered, ["public offering", "registered direct", "offering", "424b", "s-1"]):
        evidence = _matching_evidence(all_texts, ["offering", "registered direct", "424b", "s-1"])
        events.append(_event("offering", "high", 0.86, evidence, "HOLD_OR_BLOCK"))
        events.append(_event("dilution_risk", "high", 0.82, evidence, "HOLD_OR_BLOCK"))
    if _contains_any(lowered, ["reverse split", "reverse stock split"]):
        events.append(
            _event(
                "reverse_split",
                "high",
                0.85,
                _matching_evidence(all_texts, ["reverse split", "reverse stock split"]),
                "HOLD_OR_BLOCK",
            )
        )
    if _contains_any(lowered, ["delisting", "deficiency notice", "nasdaq notice"]):
        events.append(
            _event(
                "delisting_notice",
                "critical",
                0.88,
                _matching_evidence(all_texts, ["delisting", "deficiency notice", "nasdaq notice"]),
                "BLOCK_OR_HOLD",
            )
        )
    if _contains_any(lowered, ["trading halt", "halted", "halt"]):
        events.append(
            _event(
                "trading_halt",
                "critical",
                0.84,
                _matching_evidence(all_texts, ["trading halt", "halted", "halt"]),
                "BLOCK",
            )
        )
    if _contains_any(lowered, ["stock promotion", "promotional campaign", "awareness campaign", "sponsored"]):
        events.append(
            _event(
                "pump_promotion",
                "high",
                0.8,
                _matching_evidence(all_texts, ["promotion", "campaign", "sponsored"]),
                "HOLD_OR_BLOCK",
            )
        )
    if _contains_any(lowered, ["bankruptcy", "chapter 11", "going concern"]):
        events.append(
            _event(
                "bankruptcy_risk",
                "critical",
                0.86,
                _matching_evidence(all_texts, ["bankruptcy", "chapter 11", "going concern"]),
                "BLOCK_OR_HOLD",
            )
        )
    if _contains_any(lowered, ["sec investigation", "subpoena", "wells notice"]):
        events.append(
            _event(
                "sec_investigation",
                "high",
                0.82,
                _matching_evidence(all_texts, ["sec investigation", "subpoena", "wells notice"]),
                "HOLD_OR_BLOCK",
            )
        )
    return _dedupe_events(events)


def _detection_response(
    *,
    ticker: str,
    news_response: dict,
    filing_response: dict,
    events: list[dict],
    data_quality: str,
    provider_warning: str | None = None,
) -> dict:
    high_count = sum(1 for event in events if event["severity"] in {"high", "critical"})
    critical_count = sum(1 for event in events if event["severity"] == "critical")
    top_event = _top_event(events)
    return {
        "ticker": ticker,
        "provider": "risk_event_detector",
        "news_provider": news_response.get("provider"),
        "sec_filing_provider": filing_response.get("provider"),
        "data_quality": data_quality,
        "fetched_at": _now_iso(),
        "events": events,
        "event_count": len(events),
        "high_severity_event_count": high_count,
        "critical_event_count": critical_count,
        "top_event": top_event,
        "decision_impact": top_event.get("recommended_decision_impact") if top_event else "NONE",
        "provider_warning": provider_warning,
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def _event(
    event_type: str,
    severity: str,
    confidence: float,
    evidence: list[str],
    recommended_decision_impact: str,
) -> dict:
    return {
        "event_type": event_type,
        "severity": severity,
        "confidence": confidence,
        "evidence": evidence[:4],
        "recommended_decision_impact": recommended_decision_impact,
    }


def _top_event(events: list[dict]) -> dict | None:
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    if not events:
        return None
    return sorted(
        events,
        key=lambda event: (
            severity_order.get(event.get("severity"), 9),
            -float(event.get("confidence") or 0),
        ),
    )[0]


def _dedupe_events(events: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for event in events:
        event_type = event["event_type"]
        if event_type in seen:
            continue
        seen.add(event_type)
        deduped.append(event)
    return deduped


def _matching_evidence(texts: list[str], keywords: list[str]) -> list[str]:
    matches = []
    for text in texts:
        lowered = text.lower()
        if any(keyword in lowered for keyword in keywords):
            matches.append(text)
    return matches or ["Rule matched source text, but no short evidence snippet was available."]


def _combined_data_quality(news_response: dict, filing_response: dict, events: list[dict]) -> str:
    if not news_response.get("headlines") and not filing_response.get("filings"):
        return "limited"
    if any(event["event_type"] in {"no_recent_news", "insufficient_disclosure"} for event in events):
        return "limited"
    return "mock"


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _mock_headlines(ticker: str) -> list[dict]:
    now = _now_iso()
    data = {
        "TESTA": [
            {
                "title": "TESTA posts momentum update with preliminary revenue growth",
                "source": "mock_news",
                "published_at": now,
                "url": None,
            }
        ],
        "TESTB": [
            {
                "title": "TESTB announces proposed public offering",
                "source": "mock_news",
                "published_at": now,
                "url": None,
            }
        ],
        "TESTC": [
            {
                "title": "TESTC board approves reverse stock split proposal",
                "source": "mock_news",
                "published_at": now,
                "url": None,
            }
        ],
        "TESTD": [
            {
                "title": "TESTD receives Nasdaq delisting notice after deficiency period",
                "source": "mock_news",
                "published_at": now,
                "url": None,
            }
        ],
        "TESTE": [
            {
                "title": "TESTE featured in sponsored awareness campaign with promotional language",
                "source": "mock_news",
                "published_at": now,
                "url": None,
            }
        ],
    }
    return data.get(ticker, [])


def _mock_filings(ticker: str) -> list[dict]:
    data = {
        "TESTA": [
            {
                "form": "10-Q",
                "filed_at": "2026-06-01",
                "description": "Mock quarterly filing with ordinary business update.",
                "text": "TESTA quarterly update with no major risk event language.",
                "url": None,
            }
        ],
        "TESTB": [
            {
                "form": "424B",
                "filed_at": "2026-06-10",
                "description": "Prospectus supplement for proposed public offering.",
                "text": "TESTB public offering may create dilution risk for common shareholders.",
                "url": None,
            }
        ],
        "TESTC": [
            {
                "form": "DEF 14A",
                "filed_at": "2026-06-12",
                "description": "Proxy proposal requesting approval for reverse stock split.",
                "text": "TESTC seeks authority for a reverse stock split.",
                "url": None,
            }
        ],
        "TESTD": [
            {
                "form": "8-K",
                "filed_at": "2026-06-14",
                "description": "Company received Nasdaq delisting notice.",
                "text": "TESTD received a Nasdaq delisting notice and deficiency notice.",
                "url": None,
            }
        ],
        "TESTE": [
            {
                "form": "8-K",
                "filed_at": "2026-06-15",
                "description": "Mock corporate update with sponsored awareness campaign disclosure.",
                "text": "TESTE disclosed a sponsored promotional campaign.",
                "url": None,
            }
        ],
    }
    return data.get(ticker, [])


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _as_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default
