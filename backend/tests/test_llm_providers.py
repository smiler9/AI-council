from fastapi.testclient import TestClient

from app.llm.config import LLMConfig, load_llm_config
from app.llm.providers import (
    AgentLLMRequest,
    LocalOpenAICompatibleProvider,
    MockLLMProvider,
    StubLLMProvider,
    get_llm_provider,
)
from app.main import create_app
from app.seed import DEFAULT_AGENTS


def test_mock_provider_returns_structured_response():
    provider = MockLLMProvider()
    agent = DEFAULT_AGENTS[0]
    response = provider.generate_agent_response(
        AgentLLMRequest(
            meeting={
                "id": "meeting-1",
                "topic": "Review mock penny stock risk",
                "ticker": "TEST",
            },
            agent=agent,
            stage="analysis",
        )
    )

    structured = response.as_structured_response(provider.name, provider.model)
    assert structured["provider"] == "mock"
    assert structured["model"] == "mock-council-v1"
    assert structured["stance"] == "cautious"
    assert 0 <= structured["confidence"] <= 1
    assert structured["recommended_action"] == "research_only"


def test_local_provider_config_from_environment():
    config = load_llm_config(
        {
            "LLM_PROVIDER": "local_openai_compatible",
            "LLM_BASE_URL": "http://localhost:11434/v1",
            "LLM_MODEL": "qwen3-coder:30b",
            "LLM_API_KEY": "local",
            "LLM_TIMEOUT_SECONDS": "60",
        }
    )

    assert config.provider == "local_openai_compatible"
    assert config.base_url == "http://localhost:11434/v1"
    assert config.model == "qwen3-coder:30b"
    assert config.api_key == "local"
    assert config.timeout_seconds == 60


def test_provider_selection():
    assert isinstance(get_llm_provider(LLMConfig(provider="mock")), MockLLMProvider)
    assert isinstance(
        get_llm_provider(LLMConfig(provider="local_openai_compatible")),
        LocalOpenAICompatibleProvider,
    )
    assert isinstance(get_llm_provider(LLMConfig(provider="openai_stub")), StubLLMProvider)
    assert isinstance(get_llm_provider(LLMConfig(provider="anthropic_stub")), StubLLMProvider)
    assert isinstance(get_llm_provider(LLMConfig(provider="gemini_stub")), StubLLMProvider)


def test_failed_provider_handling(tmp_path):
    app = create_app(
        db_path=tmp_path / "ai_council.sqlite",
        report_dir=tmp_path / "reports",
        llm_config=LLMConfig(provider="openai_stub"),
    )

    with TestClient(app) as client:
        meeting_response = client.post(
            "/api/meetings",
            json={"topic": "Review provider failure behavior", "ticker": "FAIL"},
        )
        assert meeting_response.status_code == 201
        meeting_id = meeting_response.json()["id"]

        run_response = client.post(f"/api/meetings/{meeting_id}/run")
        assert run_response.status_code == 200
        payload = run_response.json()

    assert payload["meeting"]["status"] == "failed"
    assert payload["meeting"]["trade_review"]["order_execution_allowed"] is False
    assert payload["meeting"]["trade_review"]["provider"] == "openai_stub"
    assert payload["outputs"][0]["stance"] == "provider_error"
    assert payload["outputs"][0]["structured_response"]["error"]

