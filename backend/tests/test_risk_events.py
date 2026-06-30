from __future__ import annotations

from pathlib import Path

from app.risk_events import RiskEventConfig, detect_risk_events


def test_risk_event_status_api(client):
    response = client.get("/api/risk-events/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_news_provider"] == "mock_news_provider"
    assert payload["active_sec_filing_provider"] == "mock_sec_filing_provider"
    assert payload["detector_enabled"] is True
    assert payload["news_external_enabled"] is False
    assert payload["sec_external_enabled"] is False
    assert payload["finnhub_api_key_configured"] is False
    assert payload["polygon_api_key_configured"] is False
    assert payload["order_execution_allowed"] is False
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in payload["safety_boundary"]


def test_mock_news_provider_api(client):
    response = client.get("/api/risk-events/news/TESTB")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "TESTB"
    assert payload["provider"] == "mock_news_provider"
    assert payload["data_quality"] == "mock"
    assert "public offering" in payload["headlines"][0]["title"].lower()
    assert payload["order_execution_allowed"] is False


def test_mock_sec_filing_provider_api(client):
    response = client.get("/api/risk-events/filings/TESTC")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "TESTC"
    assert payload["provider"] == "mock_sec_filing_provider"
    assert payload["data_quality"] == "mock"
    assert payload["filings"][0]["form"] == "DEF 14A"
    assert "reverse stock split" in payload["filings"][0]["description"].lower()
    assert payload["order_execution_allowed"] is False


def test_offering_detection(client):
    response = client.get("/api/risk-events/detect/TESTB")

    assert response.status_code == 200
    payload = response.json()
    event_types = {event["event_type"] for event in payload["events"]}
    assert {"offering", "dilution_risk"}.issubset(event_types)
    assert payload["high_severity_event_count"] >= 1
    assert payload["top_event"]["severity"] == "high"
    assert payload["order_execution_allowed"] is False


def test_reverse_split_detection(client):
    response = client.get("/api/risk-events/detect/TESTC")

    assert response.status_code == 200
    payload = response.json()
    event_types = {event["event_type"] for event in payload["events"]}
    assert "reverse_split" in event_types
    assert payload["top_event"]["recommended_decision_impact"] == "HOLD_OR_BLOCK"


def test_delisting_detection(client):
    response = client.get("/api/risk-events/detect/TESTD")

    assert response.status_code == 200
    payload = response.json()
    event_types = {event["event_type"] for event in payload["events"]}
    assert "delisting_notice" in event_types
    assert payload["top_event"]["severity"] == "critical"
    assert payload["critical_event_count"] >= 1


def test_no_recent_news_detection(client):
    response = client.get("/api/risk-events/detect/NOPE")

    assert response.status_code == 200
    payload = response.json()
    event_types = {event["event_type"] for event in payload["events"]}
    assert "no_recent_news" in event_types
    assert "insufficient_disclosure" in event_types
    assert payload["data_quality"] == "limited"
    assert payload["order_execution_allowed"] is False


def test_detector_disabled_safe_response():
    payload = detect_risk_events(
        "TESTB",
        RiskEventConfig(detector_enabled=False),
    )

    assert payload["events"] == []
    assert payload["data_quality"] == "limited"
    assert payload["provider_warning"] == "Risk event detector is disabled."
    assert payload["order_execution_allowed"] is False


def test_ticker_review_includes_risk_events(client):
    response = client.post(
        "/api/ticker-reviews",
        json={"ticker": "TESTB", "review_mode": "penny_stock_risk"},
    )

    assert response.status_code == 201
    payload = response.json()
    risk_context = payload["trade_review"]["input_payload"]["risk_context"]
    event_types = {event["event_type"] for event in risk_context["risk_events"]}
    assert "offering" in event_types
    assert risk_context["detected_event_count"] >= 1
    assert risk_context["high_severity_event_count"] >= 1
    assert payload["risk_events"]["top_event"]["severity"] == "high"
    assert payload["structured_decision"]["trade_allowed"] is False
    assert payload["structured_decision"]["order_execution_allowed"] is False


def test_autonomous_review_includes_risk_events(client):
    response = client.post(
        "/api/autonomous-reviews",
        json={"universe": "mock_penny_stocks", "max_candidates": 3},
    )

    assert response.status_code == 201
    payload = response.json()
    testb = next(item for item in payload["results"] if item["ticker"] == "TESTB")
    assert testb["risk_events"]
    assert testb["top_risk_event"]["event_type"] in {"offering", "dilution_risk"}
    assert testb["risk_event_severity"] == "high"
    assert testb["order_execution_allowed"] is False


def test_critical_event_keeps_trade_allowed_false(client):
    response = client.post(
        "/api/ticker-reviews",
        json={"ticker": "TESTD", "review_mode": "penny_stock_risk"},
    )

    assert response.status_code == 201
    payload = response.json()
    decision = payload["structured_decision"]
    assert decision["risk_level"] == "critical"
    assert decision["decision"] == "BLOCK"
    assert decision["trade_allowed"] is False
    assert decision["order_execution_allowed"] is False
    assert "critical_risk_event" in decision["risk_flags"]


def test_risk_event_report_sections(client):
    created = client.post(
        "/api/ticker-reviews",
        json={"ticker": "TESTB", "review_mode": "penny_stock_risk"},
    )
    assert created.status_code == 201
    meeting_id = created.json()["ticker_review"]["linked_meeting_id"]

    report = client.get(f"/api/meetings/{meeting_id}/report")

    assert report.status_code == 200
    assert "## 뉴스/공시 리스크 이벤트" in report.text
    assert "### 감지된 리스크 이벤트" in report.text
    assert "### 주요 근거" in report.text
    assert "### 판단에 미친 영향" in report.text


def test_risk_event_code_does_not_add_broker_or_order_execution():
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
