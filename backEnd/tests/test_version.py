from app.core.config import settings


def test_version_endpoint_reports_running_release(client, monkeypatch):
    monkeypatch.setattr(settings, "app_version", "9.9.9")
    monkeypatch.setattr(settings, "deploy_track", "canary")
    response = client.get("/api/version")
    assert response.status_code == 200
    assert response.json() == {"version": "9.9.9", "track": "canary"}


def test_every_response_identifies_its_release(client, monkeypatch):
    monkeypatch.setattr(settings, "app_version", "9.9.9")
    monkeypatch.setattr(settings, "deploy_track", "blue")
    for path in ("/", "/api/health", "/api/users/me"):
        headers = client.get(path).headers
        assert headers["x-app-version"] == "9.9.9"
        assert headers["x-deploy-track"] == "blue"


def test_readiness_fails_when_database_is_unreachable(client):
    from sqlalchemy.exc import OperationalError

    from app.core.database import get_db
    from app.main import app

    class BrokenSession:
        def execute(self, *_):
            raise OperationalError("SELECT 1", {}, Exception("down"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    response = client.get("/api/health/ready")
    assert response.status_code == 503
    # Liveness must stay healthy so Kubernetes does not restart pods over a DB outage.
    assert client.get("/api/health").status_code == 200
