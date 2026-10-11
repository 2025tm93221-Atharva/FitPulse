from collections.abc import Generator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import User


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    testing_session = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        yield session


@pytest.fixture()
def client(db_engine) -> Generator[TestClient, None, None]:
    testing_session = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_account(client: TestClient, email: str, full_name: str = "Test Member", password: str = "SecurePassphrase!2026") -> dict:
    response = client.post("/api/auth/register", json={
        "email": email,
        "full_name": full_name,
        "password": password,
    })
    assert response.status_code == 201, response.text
    user = response.json()
    login_response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200, login_response.text
    return {"user": user, "token": login_response.json()["access_token"], "password": password}


@pytest.fixture()
def member_account(client):
    return create_account(client, "member@example.com")


@pytest.fixture()
def admin_account(client, db_session):
    account = create_account(client, "admin@example.com", full_name="Admin User")
    user = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    user.role = "admin"
    db_session.commit()
    login_response = client.post("/api/auth/login", json={
        "email": "admin@example.com", "password": account["password"]
    })
    assert login_response.status_code == 200
    account["token"] = login_response.json()["access_token"]
    return account


@pytest.fixture()
def staff_account(client, db_session):
    account = create_account(client, "staff@example.com", full_name="Front Desk")
    user = db_session.scalar(select(User).where(User.email == "staff@example.com"))
    user.role = "staff"
    db_session.commit()
    login_response = client.post("/api/auth/login", json={
        "email": "staff@example.com", "password": account["password"]
    })
    assert login_response.status_code == 200
    account["token"] = login_response.json()["access_token"]
    return account


def membership_payload(user_id: int, *, status: str = "active", start_date: date | None = None, expiry_date: date | None = None) -> dict:
    today = date.today()
    return {
        "user_id": user_id,
        "tier": "performance",
        "status": status,
        "start_date": (start_date or today).isoformat(),
        "expiry_date": (expiry_date or (today + timedelta(days=365))).isoformat(),
    }
