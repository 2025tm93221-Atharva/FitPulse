from datetime import date, datetime, timedelta, timezone

import jwt

from app.core.config import settings
from tests.conftest import membership_payload


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_active_membership(client, member_account, admin_account, *, start=None, expiry=None, status="active"):
    payload = membership_payload(member_account["user"]["id"], status=status, start_date=start, expiry_date=expiry)
    response = client.post("/api/memberships", headers=auth(admin_account["token"]), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_member_without_active_membership_cannot_get_qr(client, member_account):
    response = client.post("/api/check-ins/qr-token", headers=auth(member_account["token"]))
    assert response.status_code == 403


def test_member_can_get_short_lived_qr_and_staff_can_validate_once(client, member_account, admin_account, staff_account):
    membership = create_active_membership(client, member_account, admin_account)
    issued = client.post("/api/check-ins/qr-token", headers=auth(member_account["token"]))
    assert issued.status_code == 200, issued.text
    token_body = issued.json()
    assert token_body["membership_id"] == membership["id"]
    assert token_body["token_type"] == "gym_checkin"
    assert token_body["qr_token"]
    assert issued.headers["cache-control"] == "no-store, private"

    scan = client.post("/api/check-ins/validate", headers=auth(staff_account["token"]), json={
        "qr_token": token_body["qr_token"], "location_name": "Downtown Club"
    })
    assert scan.status_code == 201, scan.text
    assert scan.json()["result"] == "accepted"
    assert scan.json()["user_id"] == member_account["user"]["id"]

    replay = client.post("/api/check-ins/validate", headers=auth(staff_account["token"]), json={
        "qr_token": token_body["qr_token"], "location_name": "Downtown Club"
    })
    assert replay.status_code == 409


def test_member_cannot_call_scanner_validation_endpoint(client, member_account, admin_account):
    create_active_membership(client, member_account, admin_account)
    issued = client.post("/api/check-ins/qr-token", headers=auth(member_account["token"]))
    response = client.post("/api/check-ins/validate", headers=auth(member_account["token"]), json={
        "qr_token": issued.json()["qr_token"], "location_name": "Downtown Club"
    })
    assert response.status_code == 403


def test_expired_membership_cannot_get_qr(client, member_account, admin_account):
    create_active_membership(
        client, member_account, admin_account, status="pending",
        start=date.today() - timedelta(days=365), expiry=date.today() - timedelta(days=1),
    )
    response = client.post("/api/check-ins/qr-token", headers=auth(member_account["token"]))
    assert response.status_code == 403


def test_frozen_membership_cannot_get_qr(client, member_account, admin_account):
    create_active_membership(client, member_account, admin_account, status="pending")
    response = client.patch("/api/memberships/1/status", headers=auth(admin_account["token"]), json={"status": "active"})
    assert response.status_code == 200
    response = client.post("/api/memberships/1/freeze", headers=auth(admin_account["token"]), json={"days": 1})
    assert response.status_code == 200
    qr = client.post("/api/check-ins/qr-token", headers=auth(member_account["token"]))
    assert qr.status_code == 403


def test_expired_or_malformed_qr_is_rejected_by_staff(client, member_account, staff_account):
    malformed = client.post("/api/check-ins/validate", headers=auth(staff_account["token"]), json={
        "qr_token": "not-a-token", "location_name": "Downtown Club"
    })
    assert malformed.status_code == 401
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    expired = jwt.encode({
        "sub": str(member_account["user"]["id"]),
        "membership_id": 1,
        "token_type": "gym_checkin",
        "jti": "expired-test-token",
        "iat": past - timedelta(minutes=1),
        "exp": past,
    }, settings.secret_key, algorithm="HS256")
    response = client.post("/api/check-ins/validate", headers=auth(staff_account["token"]), json={
        "qr_token": expired, "location_name": "Downtown Club"
    })
    assert response.status_code == 401


def test_checkin_endpoint_requires_staff_or_admin(client, member_account):
    response = client.post("/api/check-ins/validate", json={"qr_token": "nope", "location_name": "Club"})
    assert response.status_code == 401


def test_checkin_history_is_scoped_to_current_user(client, member_account, admin_account, staff_account):
    create_active_membership(client, member_account, admin_account)
    issued = client.post("/api/check-ins/qr-token", headers=auth(member_account["token"])).json()
    scan = client.post("/api/check-ins/validate", headers=auth(staff_account["token"]), json={
        "qr_token": issued["qr_token"], "location_name": "Downtown Club"
    })
    assert scan.status_code == 201
    history = client.get("/api/check-ins/me", headers=auth(member_account["token"]))
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["location_name"] == "Downtown Club"


def test_membership_cancelled_after_qr_issue_cannot_be_used(client, member_account, admin_account, staff_account):
    membership = create_active_membership(client, member_account, admin_account)
    issued = client.post("/api/check-ins/qr-token", headers=auth(member_account["token"]))
    assert issued.status_code == 200
    cancelled = client.patch(
        f"/api/memberships/{membership['id']}/status",
        headers=auth(admin_account["token"]),
        json={"status": "cancelled"},
    )
    assert cancelled.status_code == 200
    response = client.post("/api/check-ins/validate", headers=auth(staff_account["token"]), json={
        "qr_token": issued.json()["qr_token"], "location_name": "Downtown Club"
    })
    assert response.status_code == 403


def test_deactivated_member_qr_is_denied_at_scan_time(client, member_account, admin_account, staff_account, db_session):
    from sqlalchemy import select
    from app.models import User

    create_active_membership(client, member_account, admin_account)
    issued = client.post("/api/check-ins/qr-token", headers=auth(member_account["token"]))
    assert issued.status_code == 200
    user = db_session.scalar(select(User).where(User.email == "member@example.com"))
    user.is_active = False
    db_session.commit()

    response = client.post("/api/check-ins/validate", headers=auth(staff_account["token"]), json={
        "qr_token": issued.json()["qr_token"], "location_name": "Downtown Club"
    })
    assert response.status_code == 403
