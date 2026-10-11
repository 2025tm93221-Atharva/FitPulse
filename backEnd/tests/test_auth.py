def test_health_and_database_readiness(client):
    assert client.get("/api/health").json()["status"] == "ok"
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_registration_hashes_password_and_does_not_expose_hash(client, db_session):
    response = client.post("/api/auth/register", json={
        "email": "  New.Member@Example.com ",
        "full_name": " New Member ",
        "password": "LongEnoughPassphrase!2026",
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "new.member@example.com"
    assert body["full_name"] == "New Member"
    assert "hashed_password" not in body
    assert "password" not in body
    assert body["role"] == "member"
    from sqlalchemy import select
    from app.models import User
    stored_user = db_session.scalar(select(User).where(User.email == "new.member@example.com"))
    assert stored_user.hashed_password.startswith("$argon2")
    assert stored_user.hashed_password != "LongEnoughPassphrase!2026"


def test_duplicate_email_is_case_insensitive(client, member_account):
    response = client.post("/api/auth/register", json={
        "email": "MEMBER@example.com",
        "full_name": "Another Name",
        "password": "AnotherSecurePass!2026",
    })
    assert response.status_code == 409


def test_password_minimum_length(client):
    response = client.post("/api/auth/register", json={
        "email": "short@example.com",
        "full_name": "Short Password",
        "password": "short",
    })
    assert response.status_code == 422


def test_login_success_returns_bearer_token(client, member_account):
    response = client.post("/api/auth/login", json={
        "email": "member@example.com",
        "password": member_account["password"],
    })
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert response.json()["user"]["email"] == "member@example.com"
    assert response.headers["cache-control"] == "no-store, private"


def test_login_failure_does_not_disclose_whether_email_exists(client, member_account):
    wrong_password = client.post("/api/auth/login", json={
        "email": "member@example.com", "password": "wrong-password"
    })
    unknown_email = client.post("/api/auth/login", json={
        "email": "unknown@example.com", "password": "wrong-password"
    })
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_profile_requires_authentication_and_returns_current_user(client, member_account):
    assert client.get("/api/users/me").status_code == 401
    response = client.get("/api/users/me", headers={"Authorization": f"Bearer {member_account['token']}"})
    assert response.status_code == 200
    assert response.json()["id"] == member_account["user"]["id"]


def test_invalid_bearer_token_is_rejected(client):
    response = client.get("/api/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_security_headers_are_present(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
