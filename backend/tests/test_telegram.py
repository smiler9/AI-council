from fastapi.testclient import TestClient

from app.llm.config import LLMConfig
from app.main import create_app
from app.services.telegram_service import (
    TelegramConfig,
    TelegramService,
    load_telegram_config,
)


def test_telegram_disabled_status(client):
    response = client.get("/api/telegram/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["configured"] is False
    assert payload["disabled_reason"] == "Telegram notifications are disabled"
    assert payload["auto_send_telegram"] is False


def test_missing_token_safe_handling():
    config = load_telegram_config(
        {
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_CHAT_ID": "12345",
            "TELEGRAM_TIMEOUT_SECONDS": "10",
        }
    )
    service = TelegramService(config)

    status = service.status()
    result = service.send_message("hello")

    assert status["enabled"] is True
    assert status["configured"] is False
    assert status["missing"] == ["TELEGRAM_BOT_TOKEN"]
    assert result["sent"] is False
    assert result["status"] == "disabled"


def test_message_formatting():
    service = TelegramService(TelegramConfig(enabled=False))
    meeting = {
        "topic": "Telegram format check",
        "mode": "risk_gate_review",
        "status": "completed",
        "trade_review": {"review_status": "completed"},
        "structured_decision": {
            "decision": "BLOCK",
            "confidence": 0.72,
            "risk_level": "critical",
            "trade_allowed": False,
            "order_execution_allowed": False,
            "primary_reasons": ["Risk gate blocked unresolved automation risk."],
            "risk_flags": ["risk_gate_blocker"],
            "required_follow_up": ["Validate data before future review."],
        },
    }

    message = service.format_meeting_message(meeting, {"path": "/tmp/report.md"})

    assert "AI Council" in message
    assert "Meeting: Telegram format check" in message
    assert "Decision: BLOCK" in message
    assert "Risk level: critical" in message
    assert "Trade allowed: false" in message
    assert "Order execution allowed: false" in message
    assert "risk_gate_blocker" in message
    assert "/tmp/report.md" in message
    assert "AI Council does not execute trades or connect to broker APIs" in message


def test_send_endpoint_disabled_mode(client, meeting):
    run_response = client.post(f"/api/meetings/{meeting['id']}/run")
    assert run_response.status_code == 200

    response = client.post(f"/api/meetings/{meeting['id']}/telegram/send")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent"] is False
    assert payload["status"] == "disabled"
    assert payload["report_available"] is True
    assert "AI Council" in payload["message"]
    assert "Order execution allowed: false" in payload["message"]


def test_telegram_meeting_not_found(client):
    response = client.post("/api/meetings/missing-id/telegram/send")

    assert response.status_code == 404


def test_telegram_service_does_not_expose_broker_or_order_execution():
    service = TelegramService(TelegramConfig(enabled=False))
    message = service.format_meeting_message(
        {
            "topic": "Safety check",
            "mode": "quick_review",
            "structured_decision": {
                "decision": "HOLD",
                "confidence": 0.5,
                "risk_level": "high",
                "trade_allowed": False,
                "order_execution_allowed": False,
                "primary_reasons": [],
                "risk_flags": [],
                "required_follow_up": [],
            },
            "trade_review": {},
        }
    )

    forbidden_terms = ["submit_order", "place_order", "BrokerClient", "OrderRequest"]
    assert all(term not in message for term in forbidden_terms)
    assert "Order execution allowed: false" in message


def test_telegram_status_with_missing_chat_id(tmp_path):
    app = create_app(
        db_path=tmp_path / "ai_council.sqlite",
        report_dir=tmp_path / "reports",
        upload_root=tmp_path / "uploads",
        llm_config=LLMConfig(provider="mock"),
        telegram_config=TelegramConfig(enabled=True, bot_token="token", chat_id=None),
    )

    with TestClient(app) as client:
        response = client.get("/api/telegram/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["configured"] is False
    assert payload["missing"] == ["TELEGRAM_CHAT_ID"]

