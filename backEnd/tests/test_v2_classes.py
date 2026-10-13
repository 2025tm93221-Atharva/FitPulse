from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import ClassBooking, ClassReminder, ClassSession, Notification
from app.core.class_reminders import process_due_class_reminders
from app.core.database import SessionLocal
from tests.conftest import create_account, membership_payload


def create_active_membership(client, admin_account, user_id):
    response = client.post(
        "/api/memberships",
        headers={"Authorization": f"Bearer {admin_account['token']}"},
        json=membership_payload(user_id),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_class(client, actor_token, *, title="Strength Foundations", starts_in_hours=8, capacity=10, waitlist_limit=10, cancellation_cutoff_minutes=120):
    starts = datetime.now(timezone.utc) + timedelta(hours=starts_in_hours)
    payload = {
        "title": title,
        "description": "Coach-led session for all levels.",
        "instructor_name": "Jordan Lee",
        "class_type": "Strength",
        "location_name": "Downtown Club",
        "starts_at": starts.isoformat(),
        "ends_at": (starts + timedelta(minutes=50)).isoformat(),
        "capacity": capacity,
        "waitlist_limit": waitlist_limit,
        "cancellation_cutoff_minutes": cancellation_cutoff_minutes,
    }
    response = client.post("/api/classes", headers={"Authorization": f"Bearer {actor_token}"}, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def auth(account):
    return {"Authorization": f"Bearer {account['token']}"}


def test_member_cannot_create_class(client, member_account):
    starts = datetime.now(timezone.utc) + timedelta(days=2)
    response = client.post("/api/classes", headers=auth(member_account), json={
        "title": "Yoga Flow", "instructor_name": "A. Coach", "class_type": "Yoga",
        "location_name": "Downtown", "starts_at": starts.isoformat(),
        "ends_at": (starts + timedelta(hours=1)).isoformat(), "capacity": 10,
    })
    assert response.status_code == 403


def test_class_creation_requires_timezone_and_future_time(client, staff_account):
    starts = datetime.now(timezone.utc) + timedelta(days=2)
    payload = {
        "title": "Yoga Flow", "instructor_name": "A. Coach", "class_type": "Yoga",
        "location_name": "Downtown", "starts_at": starts.replace(tzinfo=None).isoformat(),
        "ends_at": (starts + timedelta(hours=1)).isoformat(), "capacity": 10,
    }
    assert client.post("/api/classes", headers=auth(staff_account), json=payload).status_code == 422
    payload["starts_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert client.post("/api/classes", headers=auth(staff_account), json=payload).status_code == 422


def test_class_listing_filters_and_capacity(client, staff_account, member_account):
    created = create_class(client, staff_account["token"], capacity=4, title="Pilates Basics")
    response = client.get("/api/classes?search=Pilates", headers=auth(member_account))
    assert response.status_code == 200
    found = next(item for item in response.json() if item["id"] == created["id"])
    assert found["available_spots"] == 4
    assert found["booked_count"] == 0
    assert found["waitlist_count"] == 0
    assert client.get("/api/classes?location=nonexistent", headers=auth(member_account)).json() == []


def test_active_member_can_book_and_cannot_duplicate(client, admin_account, staff_account, member_account):
    create_active_membership(client, admin_account, member_account["user"]["id"])
    class_item = create_class(client, staff_account["token"])
    url = f"/api/classes/{class_item['id']}/bookings"
    first = client.post(url, headers=auth(member_account))
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "booked"
    duplicate = client.post(url, headers=auth(member_account))
    assert duplicate.status_code == 409
    upcoming = client.get("/api/bookings/me", headers=auth(member_account))
    assert upcoming.status_code == 200
    assert any(item["id"] == first.json()["id"] for item in upcoming.json())


def test_member_without_active_membership_cannot_book(client, staff_account, member_account):
    class_item = create_class(client, staff_account["token"])
    response = client.post(f"/api/classes/{class_item['id']}/bookings", headers=auth(member_account))
    assert response.status_code == 403


def test_waitlist_promotion_on_cancellation(client, admin_account, staff_account):
    first_user = create_account(client, "booker-one@example.com")
    second_user = create_account(client, "booker-two@example.com")
    create_active_membership(client, admin_account, first_user["user"]["id"])
    create_active_membership(client, admin_account, second_user["user"]["id"])
    class_item = create_class(client, staff_account["token"], capacity=1, waitlist_limit=2, starts_in_hours=8)
    first_booking = client.post(f"/api/classes/{class_item['id']}/bookings", headers=auth(first_user))
    second_booking = client.post(f"/api/classes/{class_item['id']}/bookings", headers=auth(second_user))
    assert first_booking.status_code == 201 and first_booking.json()["status"] == "booked"
    assert second_booking.status_code == 201 and second_booking.json()["status"] == "waitlisted"
    assert second_booking.json()["waitlist_position"] == 1

    cancelled = client.post(f"/api/bookings/{first_booking.json()['id']}/cancel", headers=auth(first_user))
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    upcoming = client.get("/api/bookings/me", headers=auth(second_user)).json()
    promoted = next(item for item in upcoming if item["id"] == second_booking.json()["id"])
    assert promoted["status"] == "booked"
    assert promoted["waitlist_position"] is None


def test_waitlist_capacity_enforced(client, admin_account, staff_account):
    accounts = [create_account(client, f"waitlist-{i}@example.com") for i in range(3)]
    for account in accounts:
        create_active_membership(client, admin_account, account["user"]["id"])
    class_item = create_class(client, staff_account["token"], capacity=1, waitlist_limit=1)
    first = client.post(f"/api/classes/{class_item['id']}/bookings", headers=auth(accounts[0]))
    second = client.post(f"/api/classes/{class_item['id']}/bookings", headers=auth(accounts[1]))
    third = client.post(f"/api/classes/{class_item['id']}/bookings", headers=auth(accounts[2]))
    assert first.status_code == second.status_code == 201
    assert third.status_code == 409


def test_cancel_cutoff_and_booking_owner_isolation(client, admin_account, staff_account):
    one = create_account(client, "cutoff-one@example.com")
    two = create_account(client, "cutoff-two@example.com")
    create_active_membership(client, admin_account, one["user"]["id"])
    create_active_membership(client, admin_account, two["user"]["id"])
    cls = create_class(client, staff_account["token"], starts_in_hours=1, cancellation_cutoff_minutes=120)
    booking = client.post(f"/api/classes/{cls['id']}/bookings", headers=auth(one)).json()
    denied = client.post(f"/api/bookings/{booking['id']}/cancel", headers=auth(one))
    assert denied.status_code == 409
    forbidden = client.post(f"/api/bookings/{booking['id']}/cancel", headers=auth(two))
    assert forbidden.status_code == 403


def test_admin_can_cancel_class_and_notifies_booked_member(client, admin_account, staff_account, member_account):
    create_active_membership(client, admin_account, member_account["user"]["id"])
    cls = create_class(client, staff_account["token"])
    booked = client.post(f"/api/classes/{cls['id']}/bookings", headers=auth(member_account)).json()
    response = client.patch(f"/api/classes/{cls['id']}", headers=auth(staff_account), json={"status": "cancelled"})
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    history = client.get("/api/bookings/me?upcoming_only=false", headers=auth(member_account)).json()
    assert next(row for row in history if row["id"] == booked["id"])["status"] == "cancelled"
    notifications = client.get("/api/notifications/me", headers=auth(member_account)).json()
    assert any(row["title"] == "Class cancelled" for row in notifications)


def test_reminders_are_scheduled_and_materialized(client, admin_account, staff_account, member_account, db_session):
    create_active_membership(client, admin_account, member_account["user"]["id"])
    cls = create_class(client, staff_account["token"], starts_in_hours=26)
    booking = client.post(f"/api/classes/{cls['id']}/bookings", headers=auth(member_account)).json()
    rows = list(db_session.scalars(select(ClassReminder).where(ClassReminder.booking_id == booking["id"])))
    assert {row.kind for row in rows} == {"24h", "2h"}
    start = datetime.fromisoformat(cls["starts_at"].replace("Z", "+00:00"))
    processed = process_due_class_reminders(db_session, now=start - timedelta(hours=23))
    assert processed >= 1
    refreshed = list(db_session.scalars(select(ClassReminder).where(ClassReminder.booking_id == booking["id"])))
    assert next(row for row in refreshed if row.kind == "24h").status == "sent"
    notifs = list(db_session.scalars(select(Notification).where(Notification.user_id == member_account["user"]["id"])))
    assert any(row.category == "class_reminder" for row in notifs)


def test_cancelled_booking_reminder_is_skipped(client, admin_account, staff_account, member_account, db_session):
    create_active_membership(client, admin_account, member_account["user"]["id"])
    cls = create_class(client, staff_account["token"], starts_in_hours=4, cancellation_cutoff_minutes=0)
    booking = client.post(f"/api/classes/{cls['id']}/bookings", headers=auth(member_account)).json()
    cancellation = client.post(f"/api/bookings/{booking['id']}/cancel", headers=auth(member_account))
    assert cancellation.status_code == 200
    reminders = list(db_session.scalars(select(ClassReminder).where(ClassReminder.booking_id == booking["id"])))
    assert all(row.status == "skipped" for row in reminders)


def test_capacity_increase_promotes_waitlist_in_order(client, admin_account, staff_account):
    first = create_account(client, "capacity-first@example.com")
    second = create_account(client, "capacity-second@example.com")
    create_active_membership(client, admin_account, first["user"]["id"])
    create_active_membership(client, admin_account, second["user"]["id"])
    cls = create_class(client, staff_account["token"], capacity=1, waitlist_limit=2, starts_in_hours=8)
    first_booking = client.post(f"/api/classes/{cls['id']}/bookings", headers=auth(first)).json()
    second_booking = client.post(f"/api/classes/{cls['id']}/bookings", headers=auth(second)).json()
    assert first_booking["status"] == "booked"
    assert second_booking["status"] == "waitlisted"
    updated = client.patch(
        f"/api/classes/{cls['id']}",
        headers=auth(staff_account),
        json={"capacity": 2},
    )
    assert updated.status_code == 200, updated.text
    refreshed = client.get("/api/bookings/me", headers=auth(second)).json()
    promoted = next(row for row in refreshed if row["id"] == second_booking["id"])
    assert promoted["status"] == "booked"
    assert updated.json()["booked_count"] == 2


def test_booking_denied_if_membership_expires_before_class(client, admin_account, staff_account, member_account):
    from datetime import date

    today = date.today()
    membership_response = client.post(
        "/api/memberships",
        headers=auth(admin_account),
        json=membership_payload(
            member_account["user"]["id"],
            status="active",
            start_date=today,
            expiry_date=today + timedelta(days=1),
        ),
    )
    assert membership_response.status_code == 201, membership_response.text
    cls = create_class(client, staff_account["token"], starts_in_hours=48)
    response = client.post(f"/api/classes/{cls['id']}/bookings", headers=auth(member_account))
    assert response.status_code == 403
    assert "expires before this class" in response.json()["detail"]


def test_cancelled_class_cannot_be_reopened(client, staff_account):
    cls = create_class(client, staff_account["token"])
    cancelled = client.patch(f"/api/classes/{cls['id']}", headers=auth(staff_account), json={"status": "cancelled"})
    assert cancelled.status_code == 200
    reopened = client.patch(f"/api/classes/{cls['id']}", headers=auth(staff_account), json={"status": "scheduled"})
    assert reopened.status_code == 409
    assert "publish a new session" in reopened.json()["detail"]
