from datetime import date, timedelta

from tests.conftest import membership_payload


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_member_cannot_create_membership(client, member_account):
    response = client.post("/api/memberships", headers=auth(member_account["token"]), json=membership_payload(member_account["user"]["id"]))
    assert response.status_code == 403


def test_admin_can_create_membership_and_member_can_list_own(client, member_account, admin_account):
    response = client.post("/api/memberships", headers=auth(admin_account["token"]), json=membership_payload(member_account["user"]["id"]))
    assert response.status_code == 201, response.text
    membership_id = response.json()["id"]

    own = client.get("/api/memberships/me", headers=auth(member_account["token"]))
    assert own.status_code == 200
    assert [m["id"] for m in own.json()] == [membership_id]


def test_membership_creation_rejects_unknown_user(client, admin_account):
    response = client.post("/api/memberships", headers=auth(admin_account["token"]), json=membership_payload(999999))
    assert response.status_code == 404


def test_membership_creation_rejects_expiry_before_start(client, member_account, admin_account):
    today = date.today()
    payload = membership_payload(member_account["user"]["id"], start_date=today, expiry_date=today - timedelta(days=1))
    response = client.post("/api/memberships", headers=auth(admin_account["token"]), json=payload)
    assert response.status_code == 422


def test_overlapping_membership_rejected(client, member_account, admin_account):
    headers = auth(admin_account["token"])
    payload = membership_payload(member_account["user"]["id"])
    assert client.post("/api/memberships", headers=headers, json=payload).status_code == 201
    response = client.post("/api/memberships", headers=headers, json=payload)
    assert response.status_code == 409


def test_member_cannot_read_another_membership(client, member_account, admin_account):
    other = client.post("/api/auth/register", json={
        "email": "other@example.com", "full_name": "Other Member", "password": "OtherStrongPassphrase!2026"
    }).json()
    membership = client.post("/api/memberships", headers=auth(admin_account["token"]), json=membership_payload(other["id"]))
    assert membership.status_code == 201
    response = client.get(f"/api/memberships/{membership.json()['id']}", headers=auth(member_account["token"]))
    assert response.status_code == 403


def test_only_admin_can_change_membership_status(client, member_account, admin_account):
    pending = membership_payload(member_account["user"]["id"], status="pending")
    created = client.post("/api/memberships", headers=auth(admin_account["token"]), json=pending)
    assert created.status_code == 201
    membership_id = created.json()["id"]
    denied = client.patch(f"/api/memberships/{membership_id}/status", headers=auth(member_account["token"]), json={"status": "active"})
    assert denied.status_code == 403
    allowed = client.patch(f"/api/memberships/{membership_id}/status", headers=auth(admin_account["token"]), json={"status": "active"})
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "active"


def test_terminal_membership_cannot_be_reactivated(client, member_account, admin_account):
    created = client.post("/api/memberships", headers=auth(admin_account["token"]), json=membership_payload(member_account["user"]["id"], status="pending"))
    membership_id = created.json()["id"]
    cancelled = client.patch(f"/api/memberships/{membership_id}/status", headers=auth(admin_account["token"]), json={"status": "cancelled"})
    assert cancelled.status_code == 200
    reactivated = client.patch(f"/api/memberships/{membership_id}/status", headers=auth(admin_account["token"]), json={"status": "active"})
    assert reactivated.status_code == 409


def test_future_membership_cannot_be_activated_today(client, member_account, admin_account):
    today = date.today()
    payload = membership_payload(member_account["user"]["id"], status="pending", start_date=today + timedelta(days=5), expiry_date=today + timedelta(days=365))
    created = client.post("/api/memberships", headers=auth(admin_account["token"]), json=payload)
    assert created.status_code == 201
    response = client.patch(f"/api/memberships/{created.json()['id']}/status", headers=auth(admin_account["token"]), json={"status": "active"})
    assert response.status_code == 409


def test_admin_cannot_create_active_membership_with_future_start_date(client, member_account, admin_account):
    today = date.today()
    payload = membership_payload(
        member_account["user"]["id"], status="active",
        start_date=today + timedelta(days=1), expiry_date=today + timedelta(days=365),
    )
    response = client.post("/api/memberships", headers=auth(admin_account["token"]), json=payload)
    assert response.status_code == 409
