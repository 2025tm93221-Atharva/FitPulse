"""Read-only checks run against a live deployment (BASE_URL), not part of the unit suite."""
import os

import httpx
import pytest


@pytest.fixture(scope="module")
def live():
    name, _, value = os.environ.get("EXTRA_HEADER", "").partition(":")
    headers = {name.strip(): value.strip()} if name else {}
    # A fresh connection per request, so load balancing is exercised.
    limits = httpx.Limits(max_keepalive_connections=0)
    with httpx.Client(base_url=os.environ["BASE_URL"], headers=headers, timeout=5, limits=limits) as client:
        yield client


def test_live_and_ready(live):
    assert live.get("/api/health").json()["status"] == "ok"
    assert live.get("/api/health/ready").json() == {"status": "ready", "database": "ok"}


def test_every_replica_serves_the_expected_version(live):
    versions = {live.get("/api/version").json()["version"] for _ in range(20)}
    assert versions == {os.environ["EXPECT_VERSION"]}


def test_database_schema_supports_login_query(live):
    response = live.post("/api/auth/login", json={"email": "smoke@example.com", "password": "not-a-real-account"})
    assert response.status_code == 401


def test_protected_routes_require_authentication(live):
    for path in ("/api/users/me", "/api/memberships/me", "/api/check-ins/me", "/api/scanner/check-ins/whoami"):
        assert live.get(path).status_code == 401


def test_security_headers(live):
    headers = live.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
