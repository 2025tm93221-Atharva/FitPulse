from datetime import date, timedelta

import pytest

from sqlalchemy import select

from app.models import PasswordResetToken, User

TEST_PASSWORD = "SecurePassphrase!2026"


def register_and_login(client, email="complete@example.com", full_name="Complete Member", password=TEST_PASSWORD):
    registered = client.post("/api/auth/register", json={
        "email": email, "full_name": full_name, "password": password,
    })
    assert registered.status_code == 201, registered.text
    logged_in = client.post("/api/auth/login", json={"email": email, "password": password})
    assert logged_in.status_code == 200, logged_in.text
    return registered.json(), logged_in.json()["access_token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def promote(client, db_session, email, role):
    response = client.post("/api/auth/register", json={
        "email": email, "full_name": f"{role.title()} Account", "password": TEST_PASSWORD,
    })
    assert response.status_code == 201, response.text
    user = db_session.scalar(select(User).where(User.email == email))
    user.role = role
    db_session.commit()
    login = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert login.status_code == 200, login.text
    return user.id, login.json()["access_token"]


def test_password_reset_is_generic_one_time_and_revokes_old_sessions(client, db_session):
    user, old_token = register_and_login(client)

    unknown = client.post("/api/auth/password-reset/request", json={"email": "nobody@example.com"})
    known = client.post("/api/auth/password-reset/request", json={"email": user["email"]})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json()["message"] == known.json()["message"]
    reset_token = known.json()["debug_reset_token"]  # Development-only; never emitted in staging/prod.
    assert reset_token

    reset = client.post("/api/auth/password-reset/confirm", json={
        "token": reset_token, "new_password": "NewSecurePassphrase!2026",
    })
    assert reset.status_code == 204
    assert client.get("/api/users/me", headers=bearer(old_token)).status_code == 401
    assert client.post("/api/auth/password-reset/confirm", json={
        "token": reset_token, "new_password": "AnotherSecurePassphrase!2026",
    }).status_code == 400
    assert client.post("/api/auth/login", json={"email": user["email"], "password": TEST_PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={
        "email": user["email"], "password": "NewSecurePassphrase!2026",
    }).status_code == 200


def test_password_reset_rejects_expired_token(client, db_session):
    user, _ = register_and_login(client, "expired-reset@example.com")
    requested = client.post("/api/auth/password-reset/request", json={"email": user["email"]})
    raw = requested.json()["debug_reset_token"]
    from hashlib import sha256
    token_row = db_session.scalar(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == sha256(raw.encode()).hexdigest()
    ))
    token_row.expires_at = token_row.created_at - timedelta(minutes=1)
    db_session.commit()
    response = client.post("/api/auth/password-reset/confirm", json={
        "token": raw, "new_password": "NewSecurePassphrase!2026",
    })
    assert response.status_code == 400


def test_member_can_edit_profile_but_not_role_or_email(client):
    user, token = register_and_login(client, "profile@example.com")
    response = client.patch("/api/users/me", headers=bearer(token), json={"full_name": "  Updated Member  "})
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Member"
    assert response.json()["email"] == user["email"]
    assert response.json()["role"] == "member"
    assert client.patch("/api/users/me", headers=bearer(token), json={"full_name": "   "}).status_code == 422
    assert client.patch("/api/users/me", headers=bearer(token), json={"role": "admin", "full_name": "Member"}).status_code == 422


def test_privacy_preferences_default_opt_out_and_persist(client):
    _, token = register_and_login(client, "privacy@example.com")
    headers = bearer(token)
    defaults = client.get("/api/privacy/preferences", headers=headers)
    assert defaults.status_code == 200
    assert defaults.json()["analytics_consent"] is False
    assert defaults.json()["marketing_consent"] is False

    saved = client.patch("/api/privacy/preferences", headers=headers, json={
        "analytics_consent": True, "marketing_consent": False,
    })
    assert saved.status_code == 200
    assert saved.json()["analytics_consent"] is True
    assert saved.json()["marketing_consent"] is False
    assert client.get("/api/privacy/preferences", headers=headers).json()["analytics_consent"] is True
    assert client.get("/api/privacy/preferences").status_code == 401


def test_support_tickets_are_private_and_staff_can_resolve(client, db_session):
    user, user_token = register_and_login(client, "support-member@example.com")
    _, staff_token = promote(client, db_session, "support-staff@example.com", "staff")
    member_headers = bearer(user_token)
    staff_headers = bearer(staff_token)

    created = client.post("/api/support/tickets", headers=member_headers, json={
        "category": "access", "subject": "QR pass not scanning", "message": "The front desk scanner rejected my new pass this morning.",
    })
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]
    own = client.get("/api/support/tickets/me", headers=member_headers)
    assert [ticket["id"] for ticket in own.json()] == [ticket_id]
    assert client.get("/api/support/tickets", headers=member_headers).status_code == 403

    staff_list = client.get("/api/support/tickets", headers=staff_headers)
    assert any(item["id"] == ticket_id for item in staff_list.json())
    resolved = client.patch(f"/api/support/tickets/{ticket_id}", headers=staff_headers, json={
        "status": "resolved", "staff_response": "We reset the reader configuration; please try again.",
    })
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["staff_response"] == "We reset the reader configuration; please try again."
    assert client.get("/api/support/tickets/me", headers=member_headers).json()[0]["status"] == "resolved"

    member_notifications = client.get("/api/notifications/me", headers=member_headers)
    assert any("Support request updated" == item["title"] for item in member_notifications.json())
    unread = client.get("/api/notifications/me?unread_only=true", headers=member_headers)
    assert unread.json()
    notification_id = unread.json()[0]["id"]
    assert client.patch(f"/api/notifications/{notification_id}/read", headers=member_headers).status_code == 200
    assert client.post("/api/notifications/me/read-all", headers=member_headers).status_code == 204
    assert client.get("/api/notifications/me?unread_only=true", headers=member_headers).json() == []


def test_end_to_end_v1_member_journey(client, db_session):
    """Acceptance path: register -> admin assigns membership -> member pass -> scan -> history/settings."""
    member, _ = register_and_login(client, "journey@example.com", "Journey Member")
    _, admin_token = promote(client, db_session, "journey-admin@example.com", "admin")

    today = date.today()
    membership = client.post("/api/memberships", headers=bearer(admin_token), json={
        "user_id": member["id"], "tier": "performance", "status": "active",
        "start_date": today.isoformat(), "expiry_date": (today + timedelta(days=365)).isoformat(),
    })
    assert membership.status_code == 201, membership.text

    login = client.post("/api/auth/login", json={"email": member["email"], "password": TEST_PASSWORD})
    member_token = login.json()["access_token"]
    member_headers = bearer(member_token)
    assert client.get("/api/memberships/me", headers=member_headers).json()[0]["tier"] == "performance"

    edited = client.patch("/api/users/me", headers=member_headers, json={"full_name": "Journey Updated"})
    assert edited.status_code == 200 and edited.json()["full_name"] == "Journey Updated"
    prefs = client.patch("/api/privacy/preferences", headers=member_headers, json={
        "analytics_consent": False, "marketing_consent": True,
    })
    assert prefs.status_code == 200 and prefs.json()["marketing_consent"] is True
    ticket = client.post("/api/support/tickets", headers=member_headers, json={
        "category": "membership", "subject": "Membership details", "message": "Please confirm my club location and entry hours.",
    })
    assert ticket.status_code == 201
    assert client.get("/api/notifications/me", headers=member_headers).status_code == 200

    pass_response = client.post("/api/check-ins/qr-token", headers=member_headers)
    assert pass_response.status_code == 200, pass_response.text
    staff_id, staff_token = promote(client, db_session, "journey-staff@example.com", "staff")
    checked = client.post("/api/check-ins/validate", headers=bearer(staff_token), json={
        "qr_token": pass_response.json()["qr_token"], "location_name": "Acceptance Test Club",
    })
    assert checked.status_code == 201, checked.text
    assert checked.json()["user_id"] == member["id"]
    assert client.post("/api/check-ins/validate", headers=bearer(staff_token), json={
        "qr_token": pass_response.json()["qr_token"], "location_name": "Acceptance Test Club",
    }).status_code == 409
    history = client.get("/api/check-ins/me", headers=member_headers)
    assert len(history.json()) == 1 and history.json()[0]["result"] == "accepted"
    assert client.get("/api/health/ready").status_code == 200


def test_password_reset_request_does_not_issue_token_for_unknown_account(client):
    response = client.post("/api/auth/password-reset/request", json={"email": "missing-v1@example.com"})
    assert response.status_code == 202
    assert response.json()["debug_reset_token"] is None



def test_new_reset_request_invalidates_previous_link(client):
    user, _ = register_and_login(client, "reset-rotation@example.com")
    first = client.post("/api/auth/password-reset/request", json={"email": user["email"]}).json()["debug_reset_token"]
    second = client.post("/api/auth/password-reset/request", json={"email": user["email"]}).json()["debug_reset_token"]
    assert first and second and first != second
    assert client.post("/api/auth/password-reset/confirm", json={
        "token": first, "new_password": "AnotherSecurePassphrase!2026",
    }).status_code == 400
    assert client.post("/api/auth/password-reset/confirm", json={
        "token": second, "new_password": "AnotherSecurePassphrase!2026",
    }).status_code == 204


def test_member_cannot_mark_another_users_notification_read(client):
    owner, owner_token = register_and_login(client, "notification-owner@example.com")
    _, other_token = register_and_login(client, "notification-other@example.com")
    notifications = client.get("/api/notifications/me", headers=bearer(owner_token)).json()
    assert notifications
    notification_id = notifications[0]["id"]
    assert client.patch(f"/api/notifications/{notification_id}/read", headers=bearer(other_token)).status_code == 403


def test_staging_console_mail_backend_is_rejected():
    from pydantic import ValidationError
    from app.core.config import Settings
    with pytest.raises(ValidationError):
        Settings(
            environment="staging",
            secret_key="a-test-only-random-secret-long-enough-for-staging-123456789",
            mail_backend="console",
        )
