import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'isolated.db'}")
    monkeypatch.setattr(settings, "auth_token", "test-only-token")
    monkeypatch.setattr(settings, "search_provider", "none")
    monkeypatch.setattr(settings, "search_endpoint", "https://api.tavily.com/search")
    monkeypatch.setattr(settings, "ai_provider", "none")
    monkeypatch.setattr(settings, "ai_endpoint", "https://api.openai.com/v1/chat/completions")
    monkeypatch.setattr(settings, "ai_model", "gpt-4o-mini")
    with TestClient(app) as test_client:
        yield test_client
