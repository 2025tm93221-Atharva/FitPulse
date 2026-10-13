"""Class reminder scheduling and delivery helpers."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.notifications import add_notification
from app.models import ClassBooking, ClassReminder, PushSubscription


def utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def schedule_class_reminders(db: Session, booking: ClassBooking, now: datetime | None = None) -> None:
    now = utc_aware(now or datetime.now(timezone.utc))
    starts_at = utc_aware(booking.class_session.starts_at)
    for kind, delta in (("24h", timedelta(hours=24)), ("2h", timedelta(hours=2))):
        scheduled_at = starts_at - delta
        if scheduled_at <= now:
            continue
        existing = db.scalar(select(ClassReminder).where(
            ClassReminder.booking_id == booking.id,
            ClassReminder.kind == kind,
        ))
        if existing is None:
            db.add(ClassReminder(
                booking_id=booking.id,
                kind=kind,
                scheduled_at=scheduled_at,
                status="pending",
            ))
        elif existing.status == "skipped":
            existing.scheduled_at = scheduled_at
            existing.status = "pending"
            existing.sent_at = None


def _send_browser_push(db: Session, user_id: int, title: str, body: str, url: str = "/#classes") -> None:
    """Send Web Push when configured; in-app notification remains the durable fallback."""
    if not settings.vapid_public_key or not settings.vapid_private_key or not settings.vapid_claims_email:
        return
    try:
        from pywebpush import WebPushException, webpush  # type: ignore[import-not-found]
    except ImportError:
        return

    subscriptions = list(db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id)))
    payload = json.dumps({"title": title, "body": body, "url": url})
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_claims_email},
                timeout=5,
            )
            subscription.last_used_at = datetime.now(timezone.utc)
        except Exception as exc:  # Push should not prevent the in-app reminder from being recorded.
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code in {404, 410}:
                db.delete(subscription)


def process_due_class_reminders(db: Session, now: datetime | None = None) -> int:
    """Materialize due reminders as in-app notifications and optional Web Push."""
    now = utc_aware(now or datetime.now(timezone.utc))
    reminders = list(db.scalars(
        select(ClassReminder)
        .options(joinedload(ClassReminder.booking).joinedload(ClassBooking.class_session))
        .where(ClassReminder.status == "pending", ClassReminder.scheduled_at <= now)
        .order_by(ClassReminder.scheduled_at.asc(), ClassReminder.id.asc())
        .limit(500)
    ))
    processed = 0
    for reminder in reminders:
        booking = reminder.booking
        session = booking.class_session
        if booking.status != "booked" or session.status != "scheduled" or utc_aware(session.starts_at) <= now:
            reminder.status = "skipped"
            processed += 1
            continue
        label = "tomorrow" if reminder.kind == "24h" else "in about 2 hours"
        title = f"Class reminder: {session.title}"
        body = f"Your {session.title} class with {session.instructor_name} at {session.location_name} starts {label}."
        add_notification(db, booking.user_id, title, body, "class_reminder")
        _send_browser_push(db, booking.user_id, title, body)
        reminder.status = "sent"
        reminder.sent_at = now
        processed += 1
    db.commit()
    return processed
