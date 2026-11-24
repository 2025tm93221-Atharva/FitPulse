from datetime import timedelta

import pytest

from app.core.clock import business_today
from tests.conftest import membership_payload


def auth(account: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {account['token']}"}


def test_summary_requires_authentication(client):
    assert client.get("/api/memberships/me/summary").status_code == 401


def test_summary_without_membership(client, member_account):
    response = client.get("/api/memberships/me/summary", headers=auth(member_account))
    assert response.json() == {"has_access": False, "tier": None, "days_remaining": 0}


@pytest.mark.parametrize(("extra_days", "expected"), [(0, 1), (29, 30)])
def test_summary_counts_days_including_today(client, member_account, admin_account, extra_days, expected):
    today = business_today()
    payload = membership_payload(
        member_account["user"]["id"], start_date=today, expiry_date=today + timedelta(days=extra_days)
    )
    assert client.post("/api/memberships", headers=auth(admin_account), json=payload).status_code == 201
    response = client.get("/api/memberships/me/summary", headers=auth(member_account))
    assert response.json() == {"has_access": True, "tier": "performance", "days_remaining": expected}


def test_pending_membership_gives_no_access(client, member_account, admin_account):
    payload = membership_payload(member_account["user"]["id"], status="pending")
    assert client.post("/api/memberships", headers=auth(admin_account), json=payload).status_code == 201
    response = client.get("/api/memberships/me/summary", headers=auth(member_account))
    assert response.json()["has_access"] is False
