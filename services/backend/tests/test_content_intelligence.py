import time

import pytest
from sqlalchemy import inspect, text

from app.models import ResearchSession
from app.services.content import ResearchOrchestrator, segment_narration
from app.services.providers import ProviderUnavailable, TavilySearchProvider, credential

AUTH = {"X-Geo-Token": "test-only-token"}


class MockSearch:
    def search(self, topic, *, limit=8):
        assert topic == "Test topic"
        assert limit == 4
        return [
            {"title": "Archive source", "url": "https://archive.example/story#top", "publisher": "Archive", "content": "On 12 March 1945, an agreement was signed.", "provenance": {"provider": "mock"}},
            {"title": "Duplicate", "url": "https://archive.example/story/", "publisher": "Archive", "content": "Duplicate result", "provenance": {"provider": "mock"}},
            {"title": "News source", "url": "https://news.example/report", "publisher": "News", "content": "Officials issued a statement.", "provenance": {"provider": "mock"}},
        ]


class MockAI:
    def generate_json(self, *, system, prompt):
        if "Extract concise" in system:
            return {"overview": "Two excerpts were collected for review.", "perspectives": ["archival", "contemporary"], "claims": [
                {"text": "An agreement was signed on 12 March 1945.", "category": "fact", "source_urls": ["https://archive.example/story"], "evidence": "On 12 March 1945, an agreement was signed."},
                {"text": "Officials issued a statement.", "category": "fact", "source_urls": ["https://news.example/report"], "evidence": "Officials issued a statement."},
            ]}
        if "Assess whether" in system:
            return {"suggested_status": "supported", "confidence": 0.81, "supporting_evidence": ["One excerpt supports it."], "contradicting_evidence": []}
        if "Write a structured" in system:
            return {"sections": {"hook": "A turning point begins.", "introduction": "This is the introduction.", "historical_background": "Background.", "main_developments": "Events unfolded.", "turning_points": "Then came a turning point.", "geopolitical_implications": "The consequences mattered.", "conclusion": "The story continues."}}
        if "single string field" in system:
            return {"content": "Regenerated and carefully sourced section."}
        if "Convert the script" in system:
            return {"scenes": [{"title": "The agreement", "script_section_key": "historical_background", "narration_text": "A treaty was signed. Its terms reshaped the region!", "description": "Show a document", "duration_seconds": 18, "visual_direction": "Archival paper texture", "historical_events": ["Signing"], "geographic_references": ["Europe"], "claim_ids": [], "source_ids": [], "transition_suggestion": "Fade through ink"}]}
        raise AssertionError(system)


def create_project(client, name="Content test", topic="Test topic"):
    response = client.post("/api/v1/projects", headers=AUTH, json={"name": name, "topic": topic, "target_duration_seconds": 300})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def mock_providers(monkeypatch):
    import app.api.routes.content as routes
    monkeypatch.setattr(routes, "configured_search_provider", MockSearch)
    monkeypatch.setattr(routes, "configured_ai_provider", MockAI)
    return routes


def research(client, project, mock_providers):
    response = client.post(f"/api/v1/projects/{project['id']}/research-sessions", headers=AUTH, json={"source_limit": 4})
    assert response.status_code == 202, response.text
    result = response.json()
    for _ in range(80):
        result = client.get(f"/api/v1/research-sessions/{result['id']}", headers=AUTH).json()
        if result["status"] in ("completed", "failed"):
            break
        time.sleep(0.025)
    assert result["status"] == "completed", result
    return result


def test_orchestrator_deduplicates_and_never_calls_search_without_provider():
    result = ResearchOrchestrator(MockSearch(), MockAI()).research("Test topic", {"source_limit": 4})
    assert [source["url"] for source in result["sources"]] == ["https://archive.example/story", "https://news.example/report"]
    assert len(result["claims"]) == 2
    assert result["claims"][0]["source_urls"] == ["https://archive.example/story"]


def test_credential_absence_is_actionable(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda *_: None)
    with pytest.raises(ProviderUnavailable, match="No tavily credential"):
        credential("tavily")


def test_search_provider_retries_only_connection_setup_failures(monkeypatch):
    import httpx
    calls = 0
    class Response:
        content = b"{}"
        def raise_for_status(self): pass
        def json(self): return {"results": [{"title": "Source", "url": "https://example.org", "content": "Excerpt"}]}
    def post(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("offline")
        return Response()
    monkeypatch.setattr("httpx.post", post)
    results = TavilySearchProvider(get_credential=lambda _: "test-only").search("Test topic", limit=1)
    assert calls == 2 and results[0]["url"] == "https://example.org"


def test_full_research_review_script_storyboard_narration_flow(client, mock_providers):
    project = create_project(client)
    session = research(client, project, mock_providers)
    assert session["overview"] == "Two excerpts were collected for review."
    sources = client.get(f"/api/v1/research-sessions/{session['id']}/sources", headers=AUTH).json()
    assert len(sources) == 2
    assert sources[0]["provenance"]["provider"] == "mock"
    claims = client.get(f"/api/v1/research-sessions/{session['id']}/claims", headers=AUTH).json()
    assert len(claims) == 2
    assert claims[0]["verification_status"] == "unverified"
    assert claims[0]["sources"][0]["url"] == "https://archive.example/story"

    check = client.post(f"/api/v1/claims/{claims[0]['id']}/fact-check", headers=AUTH)
    assert check.status_code == 200, check.text
    assert check.json()["suggested_status"] == "supported" and check.json()["review_required"] is True
    assert client.get(f"/api/v1/research-sessions/{session['id']}/claims", headers=AUTH).json()[0]["verification_status"] == "unverified"
    reviewed = client.patch(f"/api/v1/claims/{claims[0]['id']}", headers=AUTH, json={"verification_status": "supported", "reviewer_notes": "Reviewed the linked excerpt."})
    assert reviewed.status_code == 200 and reviewed.json()["reviewer_notes"] == "Reviewed the linked excerpt."

    generated = client.post(f"/api/v1/projects/{project['id']}/scripts", headers=AUTH, json={"research_session_id": session["id"]})
    assert generated.status_code == 201, generated.text
    script = generated.json()
    assert [section["section_key"] for section in script["sections"]] == ["hook", "introduction", "historical_background", "main_developments", "turning_points", "geopolitical_implications", "conclusion"]
    updated = client.patch(f"/api/v1/scripts/{script['id']}/sections/hook", headers=AUTH, json={"content": "Manually reviewed opening.", "change_note": "Editorial pass"})
    assert updated.status_code == 200 and updated.json()["sections"][0]["content"] == "Manually reviewed opening."
    assert updated.json()["sections"][0]["approved"] is False
    assert len(client.get(f"/api/v1/scripts/{script['id']}/versions", headers=AUTH).json()) == 2
    regenerated = client.post(f"/api/v1/scripts/{script['id']}/sections/hook/regenerate", headers=AUTH)
    assert regenerated.status_code == 200 and regenerated.json()["sections"][0]["content"].startswith("Regenerated")
    assert len(client.get(f"/api/v1/scripts/{script['id']}/versions", headers=AUTH).json()) == 3

    board_response = client.post(f"/api/v1/scripts/{script['id']}/storyboards", headers=AUTH)
    assert board_response.status_code == 201, board_response.text
    board = board_response.json()
    assert board["schema_version"] == "1.1" and board["scenes"][0]["scene_number"] == 1
    assert client.post(f"/api/v1/storyboards/{board['id']}/narration", headers=AUTH, json={"words_per_minute": 150}).status_code == 409
    approval = client.patch(f"/api/v1/scripts/{script['id']}/sections/historical_background/approval", headers=AUTH, json={"approved": True})
    assert approval.status_code == 200 and approval.json()["approved"] is True
    scene = board["scenes"][0]
    scene_update = {key: scene[key] for key in ("title", "script_section_key", "narration_text", "description", "duration_seconds", "visual_direction", "historical_events", "geographic_references", "claim_ids", "source_ids", "transition_suggestion")}
    scene_update["visual_direction"] = "Manual visual edit"
    assert client.patch(f"/api/v1/storyboard-scenes/{scene['id']}", headers=AUTH, json=scene_update).json()["visual_direction"] == "Manual visual edit"
    narration = client.post(f"/api/v1/storyboards/{board['id']}/narration", headers=AUTH, json={"words_per_minute": 150})
    assert narration.status_code == 200 and len(narration.json()["segments"]) == 2
    segment = narration.json()["segments"][0]
    assert segment["text"].endswith(".") and segment["paragraph_number"] == 1
    saved = client.patch(f"/api/v1/narration-segments/{segment['id']}", headers=AUTH, json={"text": "Edited narration.", "words_per_minute": 150})
    assert saved.status_code == 200 and saved.json()["text"] == "Edited narration."


def test_project_isolation_and_authentication_for_phase4(client, mock_providers):
    first, second = create_project(client, "First"), create_project(client, "Second")
    session = research(client, first, mock_providers)
    assert client.post(f"/api/v1/projects/{second['id']}/scripts", headers=AUTH, json={"research_session_id": session["id"]}).status_code == 404
    assert client.post(f"/api/v1/projects/{second['id']}/research-sessions", json={}).status_code == 401
    assert client.get("/api/v1/providers").status_code == 401


def test_provider_failure_preserves_project_and_records_failed_session(client, monkeypatch):
    import app.api.routes.content as routes
    project = create_project(client)
    class MissingProvider:
        def __init__(self):
            raise ProviderUnavailable("No tavily credential is stored in Windows Credential Manager.")
    monkeypatch.setattr(routes, "configured_search_provider", MissingProvider)
    response = client.post(f"/api/v1/projects/{project['id']}/research-sessions", headers=AUTH, json={})
    session_id = response.json()["id"]
    for _ in range(80):
        state = client.get(f"/api/v1/research-sessions/{session_id}", headers=AUTH).json()
        if state["status"] in ("failed", "completed"):
            break
        time.sleep(0.025)
    assert state["status"] == "failed"
    assert "No tavily credential" in state["error"]
    assert client.get(f"/api/v1/projects/{project['id']}", headers=AUTH).status_code == 200


def test_provider_configuration_is_persisted_without_secrets_and_validates_endpoints(client):
    payload = {"search_provider": "tavily", "search_endpoint": "https://search.example/api", "ai_provider": "openai_compatible", "ai_endpoint": "https://model.example/v1/chat/completions", "ai_model": "test-model"}
    response = client.patch("/api/v1/providers/configuration", headers=AUTH, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["search_endpoint"] == payload["search_endpoint"]
    assert response.json()["ai_model"] == "test-model"
    from app.db.session import get_session
    db = next(get_session())
    try:
        from app.models import ProviderConfiguration
        rows = db.query(ProviderConfiguration).filter(ProviderConfiguration.provider_name.in_(("search", "ai"))).all()
        assert {row.provider_name for row in rows} == {"search", "ai"}
        assert all("api_key" not in str(row.configuration).lower() for row in rows)
    finally:
        db.close()
    assert client.patch("/api/v1/providers/configuration", headers=AUTH, json={"search_endpoint": "http://example.com/search"}).status_code == 422


def test_migration_downgrade_and_upgrade_content_tables(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from app.core.config import settings

    url = f"sqlite:///{(tmp_path / 'phase4.db').as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(url)
    assert "narration_segments" in inspect(engine).get_table_names()
    command.downgrade(config, "0002_project_management")
    assert "research_sessions" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    assert "research_sessions" in inspect(engine).get_table_names()


def test_narration_sentence_segmentation_preserves_punctuation():
    assert segment_narration("First sentence. Is this disputed? Yes!\nNew paragraph.") == [
        {"paragraph_number": 1, "text": "First sentence."}, {"paragraph_number": 1, "text": "Is this disputed?"},
        {"paragraph_number": 1, "text": "Yes!"}, {"paragraph_number": 2, "text": "New paragraph."},
    ]
