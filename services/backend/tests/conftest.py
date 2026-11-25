import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'isolated.db'}")
    monkeypatch.setattr(settings, "auth_token", "test-only-token")
    with TestClient(app) as test_client:
        yield test_client

\n