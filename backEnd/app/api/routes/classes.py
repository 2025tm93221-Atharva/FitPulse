from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_roles
from app.core.class_reminders import schedule_class_reminders, utc_aware
from app.core.clock import business_today
from app.core.database import get_db
from app.core.config import settings
from app.core.notifications import add_notification
from app.models import ClassBooking, ClassSession, Membership, User
from app.schemas import ClassBookingRead, ClassSessionCreate, ClassSessionRead, ClassSessionUpdate

router = APIRouter(tags=["classes & bookings"])


def _eligible_membership(db: Session, user_id: int) -> Membership | None:
    today = business_today()
    return db.scalar(select(Membership).where(
        Membership.user_id == user_id,
        Membership.status == "active",
        Membership.start_date <= today,
        Membership.expiry_date >= today,
    ).order_by(Membership.expiry_date.desc()).limit(1))


def _session_read(db: Session, item: ClassSession) -> ClassSessionRead:
    booked_count = db.scalar(select(func.count(ClassBooking.id)).where(
        ClassBooking.class_session_id == item.id, ClassBooking.status == "booked"
    )) or 0
    waitlist_count = db.scalar(select(func.count(ClassBooking.id)).where(
        ClassBooking.class_session_id == item.id, ClassBooking.status == "waitlisted"
    )) or 0
    value = ClassSessionRead.model_validate(item)
    return value.model_copy(update={
        "booked_count": int(booked_count),
        "available_spots": max(item.capacity - int(booked_count), 0),
        "waitlist_count": int(waitlist_count),
    })


def _waitlist_position(db: Session, booking: ClassBooking) -> int | None:
    if booking.status != "waitlisted" or booking.waitlist_joined_at is None:
        return None
    ahead = db.scalar(select(func.count(ClassBooking.id)).where(
        ClassBooking.class_session_id == booking.class_session_id,
        ClassBooking.status == "waitlisted",
        (ClassBooking.waitlist_joined_at < booking.waitlist_joined_at)
        | ((ClassBooking.waitlist_joined_at == booking.waitlist_joined_at) & (ClassBooking.id < booking.id)),
    )) or 0
    return int(ahead) + 1


def _booking_read(db: Session, booking: ClassBooking) -> ClassBookingRead:
    booking = db.scalar(select(ClassBooking).options(joinedload(ClassBooking.class_session)).where(ClassBooking.id == booking.id)) or booking
    value = ClassBookingRead.model_validate(booking)
    return value.model_copy(update={
        "class_session": _session_read(db, booking.class_session),
        "waitlist_position": _waitlist_position(db, booking),
    })


def _schedule_reminders(db: Session, booking: ClassBooking, now: datetime) -> None:
    schedule_class_reminders(db, booking, now)


def _promote_waitlist(db: Session, session: ClassSession, now: datetime) -> ClassBooking | None:
    next_booking = db.scalar(select(ClassBooking).where(
        ClassBooking.class_session_id == session.id,
        ClassBooking.status == "waitlisted",
    ).order_by(ClassBooking.waitlist_joined_at.asc(), ClassBooking.created_at.asc(), ClassBooking.id.asc()).limit(1).with_for_update())
    if next_booking is None:
        return None
    next_booking.status = "booked"
    next_booking.booked_at = now
    next_booking.waitlist_joined_at = None
    next_booking.cancelled_at = None
    _schedule_reminders(db, next_booking, now)
    add_notification(
        db, next_booking.user_id, "A class spot opened up",
        f"Your waitlist spot for {session.title} is confirmed. The class starts at {utc_aware(session.starts_at).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.",
        "booking",
    )
    return next_booking


@router.get("/classes", response_model=list[ClassSessionRead])
def list_classes(
    starts_after: datetime | None = None,
    starts_before: datetime | None = None,
    location: str | None = Query(default=None, max_length=120),
    class_type: str | None = Query(default=None, max_length=60),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ClassSessionRead]:
    now = datetime.now(timezone.utc)
    lower = utc_aware(starts_after) if starts_after else now
    query = select(ClassSession).where(
        ClassSession.status == "scheduled",
        ClassSession.starts_at >= lower,
    )
    if starts_before:
        query = query.where(ClassSession.starts_at <= utc_aware(starts_before))
    if location and location.strip():
        query = query.where(ClassSession.location_name.ilike(f"%{location.strip()}%"))
    if class_type and class_type.strip():
        query = query.where(ClassSession.class_type.ilike(f"%{class_type.strip()}%"))
    if search and search.strip():
        needle = f"%{search.strip()}%"
        query = query.where((ClassSession.title.ilike(needle)) | (ClassSession.instructor_name.ilike(needle)) | (ClassSession.description.ilike(needle)))
    sessions = list(db.scalars(query.order_by(ClassSession.starts_at.asc()).limit(limit)))
    return [_session_read(db, item) for item in sessions]


@router.post("/classes", response_model=ClassSessionRead, status_code=status.HTTP_201_CREATED)
def create_class(
    payload: ClassSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
) -> ClassSessionRead:
    starts = utc_aware(payload.starts_at)
    ends = utc_aware(payload.ends_at)
    now = datetime.now(timezone.utc)
    if starts <= now:
        raise HTTPException(status_code=422, detail="Class must start in the future")
    if ends <= starts:
        raise HTTPException(status_code=422, detail="Class end time must be after its start time")
    item = ClassSession(**payload.model_dump(exclude={"starts_at", "ends_at"}), starts_at=starts, ends_at=ends, created_by_user_id=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _session_read(db, item)


@router.get("/classes/{class_id}", response_model=ClassSessionRead)
def get_class(
    class_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ClassSessionRead:
    item = db.get(ClassSession, class_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return _session_read(db, item)


@router.patch("/classes/{class_id}", response_model=ClassSessionRead)
def update_class(
    class_id: int,
    payload: ClassSessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
) -> ClassSessionRead:
    item = db.scalar(select(ClassSession).where(ClassSession.id == class_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Class not found")
    updates = payload.model_dump(exclude_unset=True)
    if item.status == "cancelled" and updates.get("status") == "scheduled":
        raise HTTPException(status_code=409, detail="A cancelled class cannot be reopened; publish a new session so members can rebook explicitly")
    if "capacity" in updates:
        booked_count = db.scalar(select(func.count(ClassBooking.id)).where(ClassBooking.class_session_id == item.id, ClassBooking.status == "booked")) or 0
        if updates["capacity"] is not None and updates["capacity"] < booked_count:
            raise HTTPException(status_code=409, detail="Capacity cannot be lower than confirmed bookings")
    if updates.get("status") == "cancelled" and item.status != "cancelled":
        if utc_aware(item.starts_at) <= datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="A started class cannot be cancelled here")
        affected = list(db.scalars(select(ClassBooking).where(
            ClassBooking.class_session_id == item.id,
            ClassBooking.status.in_(["booked", "waitlisted"]),
        )))
        for booking in affected:
            booking.status = "cancelled"
            booking.cancelled_at = datetime.now(timezone.utc)
            for reminder in booking.reminders:
                if reminder.status == "pending":
                    reminder.status = "skipped"
            add_notification(db, booking.user_id, "Class cancelled", f"{item.title} at {item.location_name} has been cancelled by the club.", "booking")
    for key, value in updates.items():
        if value is not None or key == "description":
            setattr(item, key, value)

    # If staff increases class capacity, fill newly opened spaces in waitlist order.
    if item.status == "scheduled" and "capacity" in updates:
        booked_count = int(db.scalar(select(func.count(ClassBooking.id)).where(
            ClassBooking.class_session_id == item.id,
            ClassBooking.status == "booked",
        )) or 0)
        while booked_count < item.capacity:
            promoted = _promote_waitlist(db, item, datetime.now(timezone.utc))
            if promoted is None:
                break
            db.flush()
            booked_count += 1
    db.commit()
    db.refresh(item)
    return _session_read(db, item)


@router.post("/classes/{class_id}/bookings", response_model=ClassBookingRead, status_code=status.HTTP_201_CREATED)
def book_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClassBookingRead:
    if current_user.role != "member":
        raise HTTPException(status_code=403, detail="Only member accounts can book classes")
    eligible_membership = _eligible_membership(db, current_user.id)
    if eligible_membership is None:
        raise HTTPException(status_code=403, detail="An active membership is required to book classes")
    item = db.scalar(select(ClassSession).where(ClassSession.id == class_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Class not found")
    now = datetime.now(timezone.utc)
    if item.status != "scheduled":
        raise HTTPException(status_code=409, detail="This class is not available for booking")
    if utc_aware(item.starts_at) <= now:
        raise HTTPException(status_code=409, detail="Booking is closed because the class has started")
    class_local_date = utc_aware(item.starts_at).astimezone(ZoneInfo(settings.business_timezone)).date()
    if eligible_membership.expiry_date < class_local_date:
        raise HTTPException(status_code=403, detail="Your current membership expires before this class starts. Renew your membership to book this session.")
    existing = db.scalar(select(ClassBooking).where(ClassBooking.class_session_id == item.id, ClassBooking.user_id == current_user.id).with_for_update())
    if existing is not None and existing.status != "cancelled":
        raise HTTPException(status_code=409, detail="You already have a booking or waitlist place for this class")

    booked_count = db.scalar(select(func.count(ClassBooking.id)).where(ClassBooking.class_session_id == item.id, ClassBooking.status == "booked")) or 0
    waitlist_count = db.scalar(select(func.count(ClassBooking.id)).where(ClassBooking.class_session_id == item.id, ClassBooking.status == "waitlisted")) or 0
    if booked_count < item.capacity:
        booking_status = "booked"
        joined_at = None
        booked_at = now
    elif waitlist_count < item.waitlist_limit:
        booking_status = "waitlisted"
        joined_at = now
        booked_at = None
    else:
        raise HTTPException(status_code=409, detail="This class and its waitlist are full")

    if existing is None:
        booking = ClassBooking(
            class_session_id=item.id, user_id=current_user.id, status=booking_status,
            booked_at=booked_at, waitlist_joined_at=joined_at,
        )
        db.add(booking)
        db.flush()
    else:
        booking = existing
        booking.status = booking_status
        booking.booked_at = booked_at
        booking.waitlist_joined_at = joined_at
        booking.cancelled_at = None
        booking.updated_at = now
    if booking_status == "booked":
        _schedule_reminders(db, booking, now)
        add_notification(db, current_user.id, "Class booking confirmed", f"You're booked for {item.title} at {item.location_name}.", "booking")
    else:
        add_notification(db, current_user.id, "Added to class waitlist", f"You're on the waitlist for {item.title}. Your position is shown in Upcoming Classes.", "booking")
    db.commit()
    db.refresh(booking)
    return _booking_read(db, booking)


@router.get("/bookings/me", response_model=list[ClassBookingRead])
def list_my_bookings(
    upcoming_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ClassBookingRead]:
    query = select(ClassBooking).options(joinedload(ClassBooking.class_session)).where(ClassBooking.user_id == current_user.id)
    if upcoming_only:
        query = query.where(
            ClassBooking.status.in_(["booked", "waitlisted"]),
            ClassSession.starts_at > datetime.now(timezone.utc),
        ).join(ClassSession)
    else:
        query = query.options(joinedload(ClassBooking.class_session))
    bookings = list(db.scalars(query.order_by(ClassSession.starts_at.asc()).limit(100))) if upcoming_only else list(db.scalars(query.order_by(ClassBooking.created_at.desc()).limit(100)))
    return [_booking_read(db, item) for item in bookings]


@router.post("/bookings/{booking_id}/cancel", response_model=ClassBookingRead)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClassBookingRead:
    booking = db.scalar(select(ClassBooking).options(joinedload(ClassBooking.class_session)).where(ClassBooking.id == booking_id).with_for_update())
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.user_id != current_user.id and current_user.role not in {"staff", "admin"}:
        raise HTTPException(status_code=403, detail="You cannot cancel another member's booking")
    if booking.status not in {"booked", "waitlisted"}:
        raise HTTPException(status_code=409, detail="This booking is no longer active")
    now = datetime.now(timezone.utc)
    item = booking.class_session
    if utc_aware(item.starts_at) <= now:
        raise HTTPException(status_code=409, detail="A class that has started cannot be cancelled")
    if booking.status == "booked":
        cutoff = utc_aware(item.starts_at) - timedelta(minutes=item.cancellation_cutoff_minutes)
        if now > cutoff:
            raise HTTPException(status_code=409, detail=f"Cancellation closes {item.cancellation_cutoff_minutes} minutes before class start")
    was_booked = booking.status == "booked"
    booking.status = "cancelled"
    booking.cancelled_at = now
    for reminder in booking.reminders:
        if reminder.status == "pending":
            reminder.status = "skipped"
    add_notification(db, booking.user_id, "Class booking cancelled", f"Your booking for {item.title} has been cancelled.", "booking")
    if was_booked:
        _promote_waitlist(db, item, now)
    db.commit()
    db.refresh(booking)
    return _booking_read(db, booking)
