from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.llm.config import LLMConfig
from app.main import create_app
from app.market_data import MarketDataConfig
from app.services.telegram_service import TelegramConfig
from app.webhooks import WebhookConfig


def test_diagnostics_summary_api(client):
    response = client.get("/api/diagnostics/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["backend"]["health"] == "ok"
    assert payload["providers"]["llm_provider"] == "mock"
    assert payload["providers"]["market_data_provider"] == "mock_market_data"
    assert payload["features"]["paper_trading"] is True
    assert payload["features"]["e2e_tests"] is True
    assert payload["safety"]["order_execution_allowed"] is False
    assert payload["safety"]["broker_api_connected"] is False
    assert payload["safety"]["simulation_only_confirmed"] is True
    assert payload["safety"]["secret_exposure_detected"] is False
    assert payload["order_execution_allowed"] is False
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in payload["safety_boundary"]


def test_diagnostics_security_api(client):
    response = client.get("/api/diagnostics/security")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["order_execution_allowed"] is False
    assert payload["broker_api_connected"] is False
    assert payload["order_execution_endpoints_found"] is False
    assert payload["secret_values_exposed"] is False
    assert payload["configured_secret_flags"]["telegram_bot_token_configured"] is False
    assert payload["configured_secret_flags"]["webhook_secret_configured"] is False
    assert payload["configured_secret_flags"]["market_data_api_key_configured"] is False


def test_diagnostics_providers_api(client):
    response = client.get("/api/diagnostics/providers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["providers"]["llm"]["provider"] == "mock"
    assert payload["providers"]["llm"]["external_call_performed"] is False
    assert payload["providers"]["market_data"]["active_provider"] == "mock_market_data"
    assert payload["providers"]["risk_events"]["risk_event_detector"] == "risk_event_detector"
    assert payload["providers"]["telegram"]["enabled"] is False
    assert payload["providers"]["telegram"]["token_value_exposed"] is False
    assert payload["providers"]["webhooks"]["enabled"] is False
    assert payload["providers"]["webhooks"]["secret_value_exposed"] is False
    assert payload["order_execution_allowed"] is False


def test_diagnostics_runtime_api(client):
    response = client.get("/api/diagnostics/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app_name"] == "AI Council"
    assert payload["phase_label"] == "Phase 23 diagnostics"
    assert payload["python_version"]
    assert payload["database"]["filename"].endswith(".sqlite")
    assert "/" not in payload["database"]["filename"]
    assert isinstance(payload["reports_directory_exists"], bool)
    assert payload["order_execution_allowed"] is False


def test_diagnostics_e2e_status_api(client):
    response = client.get("/api/diagnostics/e2e-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["full_e2e_script_available"] is True
    assert payload["run_full_e2e_script_path"] == "scripts/run_full_e2e.sh"
    assert payload["latest_e2e_expected_steps"] == 17
    assert payload["can_run_from_cli"] is True
    assert payload["api_does_not_run_e2e_by_default"] is True
    assert payload["order_execution_allowed"] is False


def test_diagnostics_secret_values_not_exposed(tmp_path):
    app = create_app(
        db_path=tmp_path / "ai_council.sqlite",
        report_dir=tmp_path / "reports",
        upload_root=tmp_path / "uploads",
        llm_config=LLMConfig(provider="mock", api_key="secret-llm-key"),
        telegram_config=TelegramConfig(
            enabled=True,
            bot_token="secret-telegram-token",
            chat_id="secret-chat-id",
        ),
        webhook_config=WebhookConfig(enabled=True, secret="secret-webhook-token"),
        market_data_config=MarketDataConfig(
            provider="mock_market_data",
            polygon_api_key="secret-polygon-key",
            alpaca_data_api_key="secret-alpaca-key",
            alpaca_data_api_secret="secret-alpaca-secret",
            news_provider_api_key="secret-news-key",
        ),
    )
    with TestClient(app) as test_client:
        for path in [
            "/api/diagnostics/summary",
            "/api/diagnostics/security",
            "/api/diagnostics/providers",
            "/api/diagnostics/runtime",
            "/api/diagnostics/e2e-status",
        ]:
            response = test_client.get(path)
            assert response.status_code == 200
            serialized = response.text
            assert "secret-llm-key" not in serialized
            assert "secret-telegram-token" not in serialized
            assert "secret-chat-id" not in serialized
            assert "secret-webhook-token" not in serialized
            assert "secret-polygon-key" not in serialized
            assert "secret-alpaca-key" not in serialized
            assert "secret-alpaca-secret" not in serialized
            assert "secret-news-key" not in serialized


def test_diagnostics_order_execution_allowed_always_false(client):
    for path in [
        "/api/diagnostics/summary",
        "/api/diagnostics/security",
        "/api/diagnostics/providers",
        "/api/diagnostics/runtime",
        "/api/diagnostics/e2e-status",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert _all_order_flags_false(response.json())


def test_diagnostics_cli_script_files_exist():
    root = Path(__file__).resolve().parents[2]
    assert (root / "examples" / "integration" / "run_diagnostics.py").exists()
    assert (root / "scripts" / "run_diagnostics.sh").exists()


def test_diagnostics_code_does_not_add_broker_or_order_execution():
    root = Path(__file__).resolve().parents[1] / "app"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    forbidden_terms = [
        "submit_order",
        "place_order",
        "BrokerClient",
        "OrderRequest",
        "TradingClient",
        "tradeapi.REST",
        "cancel_order",
        "execute_order",
    ]
    for term in forbidden_terms:
        assert term not in source


def _all_order_flags_false(value) -> bool:
    if isinstance(value, dict):
        if value.get("order_execution_allowed") is not None and value["order_execution_allowed"] is not False:
            return False
        return all(_all_order_flags_false(item) for item in value.values())
    if isinstance(value, list):
        return all(_all_order_flags_false(item) for item in value)
    return True
