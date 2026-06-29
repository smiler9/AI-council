from fastapi.testclient import TestClient

from app.llm.config import LLMConfig, load_llm_config
from app.llm.providers import (
    AgentLLMRequest,
    LocalOpenAICompatibleProvider,
    MockLLMProvider,
    StubLLMProvider,
    _model_ids_from_response,
    _parse_json_content,
    _safe_chat_response_metadata,
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
            "LLM_MAX_TOKENS": "512",
        }
    )

    assert config.provider == "local_openai_compatible"
    assert config.base_url == "http://localhost:11434/v1"
    assert config.model == "qwen3-coder:30b"
    assert config.api_key == "local"
    assert config.timeout_seconds == 60
    assert config.max_tokens == 512


def test_local_provider_config_rejects_invalid_base_url():
    try:
        load_llm_config(
            {
                "LLM_PROVIDER": "local_openai_compatible",
                "LLM_BASE_URL": "localhost:11434/v1",
            }
        )
    except ValueError as exc:
        assert "LLM_BASE_URL" in str(exc)
    else:
        raise AssertionError("Invalid local provider base URL should fail validation")


def test_provider_selection():
    assert isinstance(get_llm_provider(LLMConfig(provider="mock")), MockLLMProvider)
    assert isinstance(
        get_llm_provider(LLMConfig(provider="local_openai_compatible")),
        LocalOpenAICompatibleProvider,
    )
    assert isinstance(get_llm_provider(LLMConfig(provider="openai_stub")), StubLLMProvider)
    assert isinstance(get_llm_provider(LLMConfig(provider="anthropic_stub")), StubLLMProvider)
    assert isinstance(get_llm_provider(LLMConfig(provider="gemini_stub")), StubLLMProvider)


def test_local_provider_model_list_parsing_supports_openai_and_ollama_shapes():
    assert _model_ids_from_response(
        {
            "object": "list",
            "data": [
                {"id": "qwen3:8b", "object": "model"},
                {"id": "gemma4:26b-mlx", "object": "model"},
            ],
        }
    ) == ["qwen3:8b", "gemma4:26b-mlx"]

    assert _model_ids_from_response(
        {
            "models": [
                {"name": "llama3.1:8b"},
                {"model": "mistral:7b"},
            ],
        }
    ) == ["llama3.1:8b", "mistral:7b"]


def test_local_provider_json_parser_handles_thinking_and_markdown_wrappers():
    parsed = _parse_json_content(
        """
        <think>private reasoning omitted</think>
        ```json
        {
          "stance": "cautious",
          "confidence": 0.4,
          "content": "Review only.",
          "risk_flags": ["limited_data"],
          "evidence_gaps": ["filings"],
          "recommended_action": "needs_more_evidence"
        }
        ```
        """
    )

    assert parsed["stance"] == "cautious"
    assert parsed["confidence"] == 0.4


def test_local_provider_json_parser_prefers_agent_response_schema():
    parsed = _parse_json_content(
        """
        Input was {"meeting": {"topic": "ignore this echoed payload"}}.
        Final answer:
        {
          "stance": "no_position",
          "confidence": 0.2,
          "content": "Evidence is insufficient for anything beyond review.",
          "risk_flags": ["insufficient_data"],
          "evidence_gaps": ["filings"],
          "recommended_action": "needs_more_evidence"
        }
        """
    )

    assert parsed["stance"] == "no_position"
    assert parsed["content"].startswith("Evidence is insufficient")


def test_local_provider_raw_metadata_does_not_store_reasoning_text():
    metadata = _safe_chat_response_metadata(
        {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": "qwen3:8b",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"stance":"ok"}',
                        "reasoning": "private chain-of-thought should not be stored",
                    },
                }
            ],
            "usage": {"total_tokens": 42},
        }
    )

    provider_response = metadata["provider_response"]
    assert provider_response["has_reasoning"] is True
    assert provider_response["content_length"] == len('{"stance":"ok"}')
    assert "private chain-of-thought" not in str(metadata)


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


def test_local_provider_unavailable_meeting_fails_safely(tmp_path):
    app = create_app(
        db_path=tmp_path / "ai_council.sqlite",
        report_dir=tmp_path / "reports",
        llm_config=LLMConfig(
            provider="local_openai_compatible",
            base_url="http://127.0.0.1:9/v1",
            model="phase6-unavailable-test",
            api_key="local",
            timeout_seconds=0.1,
        ),
    )

    with TestClient(app) as client:
        meeting_response = client.post(
            "/api/meetings",
            json={
                "topic": "Verify local provider unavailable handling",
                "ticker": "LLM",
                "mode": "deep_debate",
            },
        )
        assert meeting_response.status_code == 201
        meeting_id = meeting_response.json()["id"]

        run_response = client.post(f"/api/meetings/{meeting_id}/run")
        assert run_response.status_code == 200
        payload = run_response.json()

    assert payload["meeting"]["status"] == "failed"
    assert payload["meeting"]["trade_review"]["provider"] == "local_openai_compatible"
    assert payload["meeting"]["trade_review"]["order_execution_allowed"] is False
    assert payload["structured_decision"]["decision"] == "NEED_MORE_DATA"
    assert payload["structured_decision"]["order_execution_allowed"] is False
    assert payload["structured_decision"]["safety_boundary"]
    assert payload["outputs"][0]["structured_response"]["error"]
