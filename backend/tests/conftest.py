from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.llm.config import LLMConfig
from app.main import create_app
from app.services.telegram_service import TelegramConfig


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        db_path=tmp_path / "ai_council.sqlite",
        report_dir=tmp_path / "reports",
        upload_root=tmp_path / "uploads",
        llm_config=LLMConfig(provider="mock"),
        telegram_config=TelegramConfig(enabled=False),
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def meeting(client):
    response = client.post(
        "/api/meetings",
        json={"topic": "Assess a mock penny stock breakout", "ticker": "TEST"},
    )
    assert response.status_code == 201
    return response.json()
