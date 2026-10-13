from datetime import date, timedelta

from app.models import Membership
from tests.conftest import create_account, membership_payload


def auth(account):
    return {"Authorization": f"Bearer {account['token']}"}


def create_active_membership(client, admin_account, account, expiry_days=365):
    today = date.today()
    payload = membership_payload(account["user"]["id"], expiry_date=today + timedelta(days=expiry_days))
    response = client.post("/api/memberships", headers=auth(admin_account), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_member_can_request_renewal_and_admin_approve(client, admin_account, member_account, db_session):
    membership = create_active_membership(client, admin_account, member_account)
    before = date.fromisoformat(membership["expiry_date"])
    response = client.post(f"/api/memberships/{membership['id']}/renew", headers=auth(member_account), json={"renewal_days": 365})
    assert response.status_code == 201, response.text
    request = response.json()
    assert request["status"] == "pending"
    duplicate = client.post(f"/api/memberships/{membership['id']}/renew", headers=auth(member_account), json={"renewal_days": 30})
    assert duplicate.status_code == 409
    reviewed = client.patch(f"/api/memberships/renewals/{request['id']}", headers=auth(admin_account), json={"status": "approved"})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"
    db_session.refresh(db_session.get(Membership, membership["id"]))
    actual = db_session.get(Membership, membership["id"])
    assert actual.expiry_date == before + timedelta(days=365)
    assert actual.status == "active"


def test_member_can_cancel_pending_renewal_request(client, admin_account, member_account):
    membership = create_active_membership(client, admin_account, member_account)
    created = client.post(f"/api/memberships/{membership['id']}/renew", headers=auth(member_account), json={"renewal_days": 90})
    cancelled = client.post(f"/api/memberships/renewals/{created.json()['id']}/cancel", headers=auth(member_account))
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_member_cannot_renew_another_membership(client, admin_account, member_account):
    other = create_account(client, "renew-other@example.com")
    membership = create_active_membership(client, admin_account, other)
    response = client.post(f"/api/memberships/{membership['id']}/renew", headers=auth(member_account), json={"renewal_days": 30})
    assert response.status_code == 403


def test_freeze_and_resume_extend_expiry_by_actual_frozen_days(client, admin_account, member_account, db_session):
    membership_json = create_active_membership(client, admin_account, member_account)
    membership = db_session.get(Membership, membership_json["id"])
    original_expiry = membership.expiry_date
    freeze = client.post(f"/api/memberships/{membership.id}/freeze", headers=auth(member_account), json={"days": 7})
    assert freeze.status_code == 200, freeze.text
    assert freeze.json()["status"] == "frozen"
    membership.freeze_start_date = date.today() - timedelta(days=3)
    membership.freeze_until_date = date.today() + timedelta(days=4)
    db_session.commit()
    resumed = client.post(f"/api/memberships/{membership.id}/resume", headers=auth(member_account))
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "active"
    assert date.fromisoformat(resumed.json()["expiry_date"]) == original_expiry + timedelta(days=3)
    assert resumed.json()["freeze_start_date"] is None
    assert resumed.json()["freeze_until_date"] is None


def test_freeze_duration_validation(client, admin_account, member_account):
    membership = create_active_membership(client, admin_account, member_account)
    response = client.post(f"/api/memberships/{membership['id']}/freeze", headers=auth(member_account), json={"days": 90})
    assert response.status_code == 422


def test_only_owner_or_staff_can_freeze(client, admin_account, member_account):
    other = create_account(client, "freeze-other@example.com")
    membership = create_active_membership(client, admin_account, other)
    response = client.post(f"/api/memberships/{membership['id']}/freeze", headers=auth(member_account), json={"days": 5})
    assert response.status_code == 403


def test_frozen_membership_cannot_resume_twice(client, admin_account, member_account):
    membership = create_active_membership(client, admin_account, member_account)
    client.post(f"/api/memberships/{membership['id']}/freeze", headers=auth(member_account), json={"days": 5})
    first = client.post(f"/api/memberships/{membership['id']}/resume", headers=auth(member_account))
    second = client.post(f"/api/memberships/{membership['id']}/resume", headers=auth(member_account))
    assert first.status_code == 200
    assert second.status_code == 409


def test_scheduled_freeze_automatically_resumes_membership(client, admin_account, member_account, db_session):
    from app.tasks import process_due_membership_resumes

    membership_json = create_active_membership(client, admin_account, member_account)
    frozen = client.post(f"/api/memberships/{membership_json['id']}/freeze", headers=auth(member_account), json={"days": 7})
    assert frozen.status_code == 200
    membership = db_session.get(Membership, membership_json["id"])
    original_expiry = membership.expiry_date
    membership.freeze_start_date = date.today() - timedelta(days=7)
    membership.freeze_until_date = date.today()
    db_session.commit()
    count = process_due_membership_resumes(db_session, today=date.today())
    db_session.refresh(membership)
    assert count == 1
    assert membership.status == "active"
    assert membership.expiry_date == original_expiry + timedelta(days=7)
    assert membership.freeze_start_date is None and membership.freeze_until_date is None


def test_freeze_is_rejected_when_class_booking_overlaps_freeze_window(client, admin_account, staff_account, member_account):

    from tests.test_v2_classes import create_class

    membership = create_active_membership(client, admin_account, member_account)
    cls = create_class(client, staff_account["token"], starts_in_hours=72)
    booking = client.post(f"/api/classes/{cls['id']}/bookings", headers=auth(member_account))
    assert booking.status_code == 201
    response = client.post(f"/api/memberships/{membership['id']}/freeze", headers=auth(member_account), json={"days": 5})
    assert response.status_code == 409
    assert "Cancel class bookings" in response.json()["detail"]


def test_admin_status_endpoint_cannot_bypass_freeze_lifecycle(client, admin_account, member_account):
    membership = create_active_membership(client, admin_account, member_account)
    response = client.patch(
        f"/api/memberships/{membership['id']}/status",
        headers=auth(admin_account),
        json={"status": "frozen"},
    )
    assert response.status_code == 409
    assert "freeze endpoint" in response.json()["detail"]
    current = client.get(f"/api/memberships/{membership['id']}", headers=auth(member_account))
    assert current.status_code == 200
    assert current.json()["status"] == "active"
    assert current.json()["freeze_start_date"] is None
    assert current.json()["freeze_until_date"] is None


def test_renewal_approval_cannot_overlap_another_membership(client, admin_account, member_account):
    active = create_active_membership(client, admin_account, member_account, expiry_days=5)
    active_expiry = date.fromisoformat(active["expiry_date"])
    future = client.post(
        "/api/memberships",
        headers=auth(admin_account),
        json=membership_payload(
            member_account["user"]["id"],
            status="pending",
            start_date=active_expiry + timedelta(days=1),
            expiry_date=active_expiry + timedelta(days=365),
        ),
    )
    assert future.status_code == 201, future.text
    request = client.post(f"/api/memberships/{active['id']}/renew", headers=auth(member_account), json={"renewal_days": 30})
    assert request.status_code == 201, request.text
    review = client.patch(
        f"/api/memberships/renewals/{request.json()['id']}",
        headers=auth(admin_account),
        json={"status": "approved"},
    )
    assert review.status_code == 409
    assert "overlap another" in review.json()["detail"]
    requests = client.get("/api/memberships/renewals/me", headers=auth(member_account)).json()
    assert next(item for item in requests if item["id"] == request.json()["id"])["status"] == "pending"
