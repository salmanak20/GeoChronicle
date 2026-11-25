from datetime import UTC, datetime

import pytest


AUTH = {"X-Geo-Token": "test-only-token"}


def create(client, name="Silk Road", **extra):
    response = client.post("/api/v1/projects", headers=AUTH, json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_project_defaults_and_utc_timestamps(client):
    project = create(client, "  Silk Road  ", topic="Trade routes")
    assert project["name"] == "Silk Road"
    assert project["status"] == "draft"
    assert project["aspect_ratio"] == "16:9"
    assert project["language"] == "en"
    assert project["visual_style"] == "hybrid"
    assert project["created_at"].endswith("Z")
    assert datetime.fromisoformat(project["created_at"].replace("Z", "+00:00")).tzinfo == UTC


@pytest.mark.parametrize("payload", [{}, {"name": "   "}, {"name": "x" * 201}, {"name": "valid", "target_duration_seconds": 10}, {"name": "valid", "aspect_ratio": "21:9"}, {"name": "valid", "unexpected": "field"}])
def test_create_rejects_missing_or_invalid_project_data(client, payload):
    assert client.post("/api/v1/projects", headers=AUTH, json=payload).status_code == 422


def test_list_pagination_search_status_and_sorting(client):
    first = create(client, "Silk Road", topic="Central Asia")
    second = create(client, "Ottoman Empire", topic="Europe")
    third = create(client, "Trade route map", topic="Asia")
    client.patch(f"/api/v1/projects/{second['id']}", headers=AUTH, json={"status": "in_progress"})
    client.patch(f"/api/v1/projects/{third['id']}", headers=AUTH, json={"status": "completed"})
    from app.db.session import get_engine
    from sqlalchemy import text
    with get_engine().begin() as connection:
        for project, created_at in ((first, "2025-01-01 00:00:00"), (second, "2025-01-02 00:00:00"), (third, "2025-01-03 00:00:00")):
            connection.execute(text("UPDATE projects SET created_at = :created_at WHERE id = :id"), {"id": project["id"], "created_at": created_at})

    page = client.get("/api/v1/projects?page=1&page_size=2&sort_by=created_at&sort_order=asc", headers=AUTH).json()
    assert page["total"] == 3 and page["pages"] == 2
    assert [item["id"] for item in page["items"]] == [first["id"], second["id"]]
    found = client.get("/api/v1/projects?search=asia", headers=AUTH).json()
    assert found["total"] == 2
    filtered = client.get("/api/v1/projects?status=in_progress", headers=AUTH).json()
    assert [item["id"] for item in filtered["items"]] == [second["id"]]
    topic_match = client.get("/api/v1/projects?search=Europe", headers=AUTH).json()
    assert [item["id"] for item in topic_match["items"]] == [second["id"]]


def test_list_rejects_invalid_pagination_and_sort_fields(client):
    assert client.get("/api/v1/projects?page=0", headers=AUTH).status_code == 422
    assert client.get("/api/v1/projects?sort_by=name", headers=AUTH).status_code == 422


def test_get_update_partial_and_updated_timestamp(client):
    project = create(client, "Original", topic="Original topic")
    updated = client.patch(f"/api/v1/projects/{project['id']}", headers=AUTH, json={"name": "Revised", "status": "archived"})
    assert updated.status_code == 200
    data = updated.json()
    assert data["name"] == "Revised"
    assert data["topic"] == "Original topic"
    assert data["status"] == "archived"
    assert data["updated_at"] >= project["updated_at"]
    assert client.get(f"/api/v1/projects/{project['id']}", headers=AUTH).json() == data


@pytest.mark.parametrize("payload", [{}, {"name": " "}, {"status": "rendering"}, {"target_duration_seconds": 9000}, {"aspect_ratio": None}])
def test_update_rejects_invalid_changes(client, payload):
    project = create(client, "Stable")
    assert client.patch(f"/api/v1/projects/{project['id']}", headers=AUTH, json=payload).status_code == 422


def test_get_and_delete_nonexistent_project_return_404(client):
    assert client.get("/api/v1/projects/9999", headers=AUTH).status_code == 404
    assert client.delete("/api/v1/projects/9999", headers=AUTH).status_code == 404


def test_delete_removes_only_target_and_stats_update(client):
    first = create(client, "Keep")
    second = create(client, "Remove")
    client.patch(f"/api/v1/projects/{first['id']}", headers=AUTH, json={"status": "in_progress"})
    client.patch(f"/api/v1/projects/{second['id']}", headers=AUTH, json={"status": "completed"})
    stats = client.get("/api/v1/projects/stats", headers=AUTH).json()
    assert (stats["total"], stats["draft"], stats["in_progress"], stats["completed"]) == (2, 0, 1, 1)
    assert len(stats["recently_updated"]) == 2
    assert client.delete(f"/api/v1/projects/{second['id']}", headers=AUTH).status_code == 204
    assert client.get(f"/api/v1/projects/{first['id']}", headers=AUTH).status_code == 200
    assert client.get(f"/api/v1/projects/{second['id']}", headers=AUTH).status_code == 404
    assert client.get("/api/v1/projects/stats", headers=AUTH).json()["total"] == 1


@pytest.mark.parametrize("method,path,kwargs", [
    ("get", "/api/v1/projects", {}),
    ("get", "/api/v1/projects/stats", {}),
    ("post", "/api/v1/projects", {"json": {"name": "unauthenticated"}}),
])
def test_project_endpoints_require_valid_authentication(client, method, path, kwargs):
    assert getattr(client, method)(path, **kwargs).status_code == 401
    assert getattr(client, method)(path, headers={"X-Geo-Token": "wrong"}, **kwargs).status_code == 401


def test_existing_phase2_project_is_preserved_by_upgrade(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from app.core.config import settings

    database = tmp_path / "phase2-existing.db"
    url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0001_initial")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO projects (name, status) VALUES ('Existing project', 'draft')"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(text("SELECT name, status, aspect_ratio, language, visual_style FROM projects")).one()
    assert tuple(row) == ("Existing project", "draft", "16:9", "en", "hybrid")
