def test_health_readiness_and_auth(client):
    headers = {"X-Geo-Token": "test-only-token"}
    assert client.get("/api/v1/health", headers=headers).json()["database"] == "connected"
    assert client.get("/api/v1/health/ready", headers=headers).status_code == 200
    assert client.get("/api/v1/health").status_code == 401
    assert client.get("/api/v1/health", headers={"X-Geo-Token": "invalid"}).status_code == 401


def test_readiness_when_database_unavailable(client):
    class UnavailableSession:
        def execute(self, _query):
            raise RuntimeError("database unavailable")

    def unavailable():
        yield UnavailableSession()

    from app.api.routes import health
    client.app.dependency_overrides[health.get_session] = unavailable
    response = client.get("/api/v1/health/ready", headers={"X-Geo-Token": "test-only-token"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"
    client.app.dependency_overrides.pop(health.get_session)


def test_shutdown_requires_valid_launch_token(client):
    class Server:
        should_exit = False

    server = Server()
    client.app.state.uvicorn_server = server
    assert client.post("/api/v1/internal/shutdown").status_code == 401
    assert client.post("/api/v1/internal/shutdown", headers={"X-Geo-Token": "invalid"}).status_code == 401
    assert client.post("/api/v1/internal/shutdown", headers={"X-Geo-Token": "test-only-token"}).status_code == 202
    assert server.should_exit
    del client.app.state.uvicorn_server
