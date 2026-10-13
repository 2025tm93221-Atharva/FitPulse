from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.clock import business_now, business_today
from app.core.config import settings
from app.core.database import get_db
from app.core.notifications import add_notification
from app.models import ClassBooking, ClassSession, Membership, MembershipRenewalRequest, User
from app.schemas import (MembershipCreate, MembershipFreezeRequest, MembershipRead, MembershipRenewalCreate, MembershipRenewalRead, MembershipRenewalReview, MembershipStatusUpdate)

router = APIRouter(prefix="/memberships", tags=["memberships"])
ALLOWED_TRANSITIONS = {
    "pending": {"active", "cancelled"},
    "active": {"cancelled", "expired"},
    "frozen": {"cancelled", "expired"},
    "cancelled": set(),
    "expired": set(),
}


@router.get("/me", response_model=list[MembershipRead])
def list_my_memberships(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Membership]:
    return list(db.scalars(
        select(Membership).where(Membership.user_id == current_user.id)
        .order_by(Membership.created_at.desc())
    ))


@router.post("", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
def create_membership(
    payload: MembershipCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> Membership:
    if payload.expiry_date < payload.start_date:
        raise HTTPException(status_code=422, detail="expiry_date cannot be before start_date")
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=409, detail="Cannot create a membership for an inactive account")
    if payload.status == "active":
        today = business_today()
        if payload.start_date > today or payload.expiry_date < today:
            raise HTTPException(status_code=409, detail="Active membership dates must include today")

    # Avoid overlapping non-terminal memberships for the same account.
    overlapping = db.scalar(select(Membership.id).where(
        Membership.user_id == payload.user_id,
        Membership.status.in_(["pending", "active", "frozen"]),
        Membership.start_date <= payload.expiry_date,
        Membership.expiry_date >= payload.start_date,
    ).limit(1))
    if overlapping is not None:
        raise HTTPException(status_code=409, detail="Membership dates overlap an existing pending or usable membership")

    membership = Membership(**payload.model_dump())
    db.add(membership)
    db.flush()
    add_notification(
        db, user.id, "Membership created",
        f"Your {membership.tier} membership is {membership.status}.", "membership",
    )
    db.commit()
    db.refresh(membership)
    return membership



@router.get("/renewals/me", response_model=list[MembershipRenewalRead])
def list_my_renewal_requests(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[MembershipRenewalRequest]:
    return list(db.scalars(
        select(MembershipRenewalRequest).where(MembershipRenewalRequest.user_id == current_user.id)
        .order_by(MembershipRenewalRequest.created_at.desc()).limit(100)
    ))


@router.get("/renewals", response_model=list[MembershipRenewalRead])
def list_renewal_requests(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("staff", "admin")),
) -> list[MembershipRenewalRequest]:
    query = select(MembershipRenewalRequest)
    if status_filter:
        if status_filter not in {"pending", "approved", "rejected", "cancelled"}:
            raise HTTPException(status_code=422, detail="Invalid renewal request status filter")
        query = query.where(MembershipRenewalRequest.status == status_filter)
    return list(db.scalars(query.order_by(MembershipRenewalRequest.created_at.asc()).limit(200)))


@router.patch("/renewals/{request_id}", response_model=MembershipRenewalRead)
def review_renewal_request(
    request_id: int,
    payload: MembershipRenewalReview,
    db: Session = Depends(get_db),
    reviewer: User = Depends(require_roles("staff", "admin")),
) -> MembershipRenewalRequest:
    request = db.scalar(select(MembershipRenewalRequest).where(MembershipRenewalRequest.id == request_id).with_for_update())
    if request is None:
        raise HTTPException(status_code=404, detail="Renewal request not found")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending renewal requests can be reviewed")
    membership = db.get(Membership, request.membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    if payload.status == "approved":
        if membership.status not in {"active", "expired"}:
            raise HTTPException(status_code=409, detail="Only active or expired memberships can be renewed")
        today = business_today()
        proposed_expiry = max(membership.expiry_date, today) + timedelta(days=request.renewal_days)
        overlap_id = db.scalar(select(Membership.id).where(
            Membership.user_id == membership.user_id,
            Membership.id != membership.id,
            Membership.status.in_(["pending", "active", "frozen"]),
            Membership.start_date <= proposed_expiry,
            Membership.expiry_date >= membership.start_date,
        ).limit(1))
        if overlap_id is not None:
            raise HTTPException(status_code=409, detail="Renewal would overlap another pending or usable membership. Resolve the other membership first.")
        membership.expiry_date = proposed_expiry
        membership.status = "active"
        membership.freeze_start_date = None
        membership.freeze_until_date = None
    request.status = payload.status
    request.reviewed_by_user_id = reviewer.id
    request.reviewed_at = datetime.now(timezone.utc)
    message = (
        f"Your membership renewal for {request.renewal_days} days was approved. New expiry date: {membership.expiry_date}."
        if payload.status == "approved" else "Your membership renewal request was not approved. Contact the club if you need more information."
    )
    add_notification(db, request.user_id, "Membership renewal update", message, "membership")
    db.commit()
    db.refresh(request)
    return request


@router.post("/renewals/{request_id}/cancel", response_model=MembershipRenewalRead)
def cancel_renewal_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MembershipRenewalRequest:
    request = db.get(MembershipRenewalRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Renewal request not found")
    if request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot cancel another member's renewal request")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending renewal requests can be cancelled")
    request.status = "cancelled"
    request.reviewed_at = datetime.now(timezone.utc)
    add_notification(db, current_user.id, "Renewal request cancelled", "Your pending membership renewal request was cancelled.", "membership")
    db.commit()
    db.refresh(request)
    return request


@router.get("/{membership_id}", response_model=MembershipRead)
def get_membership(
    membership_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Membership:
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    if current_user.role != "admin" and membership.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot access another member's membership")
    return membership


@router.patch("/{membership_id}/status", response_model=MembershipRead)
def update_membership_status(
    membership_id: int,
    payload: MembershipStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> Membership:
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    if payload.status == membership.status:
        return membership
    # Freeze/resume transitions carry dates and expiry adjustments; they must use
    # the dedicated self-service endpoints rather than changing only the status.
    if payload.status == "frozen":
        raise HTTPException(status_code=409, detail="Use the membership freeze endpoint so freeze dates are recorded")
    if membership.status == "frozen" and payload.status == "active":
        raise HTTPException(status_code=409, detail="Use the membership resume endpoint so frozen days are reconciled")
    if payload.status not in ALLOWED_TRANSITIONS.get(membership.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid membership status transition: {membership.status} -> {payload.status}",
        )
    if payload.status == "active":
        today = business_today()
        if membership.start_date > today or membership.expiry_date < today:
            raise HTTPException(status_code=409, detail="Membership dates do not allow activation today")
        overlap_id = db.scalar(select(Membership.id).where(
            Membership.user_id == membership.user_id,
            Membership.id != membership.id,
            Membership.status.in_(["pending", "active", "frozen"]),
            Membership.start_date <= membership.expiry_date,
            Membership.expiry_date >= membership.start_date,
        ).limit(1))
        if overlap_id is not None:
            raise HTTPException(status_code=409, detail="Member already has an overlapping active membership")
    membership.status = payload.status
    if payload.status in {"cancelled", "expired"}:
        membership.freeze_start_date = None
        membership.freeze_until_date = None
    add_notification(
        db, membership.user_id, "Membership status updated",
        f"Your {membership.tier} membership status is now {membership.status}.", "membership",
    )
    db.commit()
    db.refresh(membership)
    return membership


@router.post("/{membership_id}/renew", response_model=MembershipRenewalRead, status_code=status.HTTP_201_CREATED)
def request_membership_renewal(
    membership_id: int,
    payload: MembershipRenewalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MembershipRenewalRequest:
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    if membership.user_id != current_user.id and current_user.role not in {"staff", "admin"}:
        raise HTTPException(status_code=403, detail="You cannot renew another member's membership")
    if membership.status not in {"active", "expired"}:
        raise HTTPException(status_code=409, detail="Only active or expired memberships can request renewal")
    pending = db.scalar(select(MembershipRenewalRequest.id).where(
        MembershipRenewalRequest.membership_id == membership.id,
        MembershipRenewalRequest.status == "pending",
    ).limit(1))
    if pending is not None:
        raise HTTPException(status_code=409, detail="A renewal request is already pending for this membership")
    request = MembershipRenewalRequest(
        membership_id=membership.id,
        user_id=membership.user_id,
        renewal_days=payload.renewal_days,
        status="pending",
    )
    db.add(request)
    add_notification(
        db, membership.user_id, "Renewal request received",
        f"Your request to renew for {payload.renewal_days} days is awaiting club confirmation. No payment has been taken.",
        "membership",
    )
    db.commit()
    db.refresh(request)
    return request


@router.post("/{membership_id}/freeze", response_model=MembershipRead)
def freeze_membership(
    membership_id: int,
    payload: MembershipFreezeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Membership:
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    if membership.user_id != current_user.id and current_user.role not in {"admin", "staff"}:
        raise HTTPException(status_code=403, detail="You cannot freeze another member's membership")
    today = business_today()
    if membership.status != "active" or membership.start_date > today or membership.expiry_date < today:
        raise HTTPException(status_code=409, detail="Only a currently active membership can be frozen")
    start_at = datetime.now(timezone.utc)
    until = today + timedelta(days=payload.days)
    end_exclusive = datetime.combine(until, time.min, tzinfo=ZoneInfo(settings.business_timezone)).astimezone(timezone.utc)
    conflict = db.scalar(select(ClassBooking.id).join(ClassSession).where(
        ClassBooking.user_id == membership.user_id,
        ClassBooking.status.in_(["booked", "waitlisted"]),
        ClassSession.status == "scheduled",
        ClassSession.starts_at > start_at,
        ClassSession.starts_at < end_exclusive,
    ).limit(1))
    if conflict is not None:
        raise HTTPException(status_code=409, detail="Cancel class bookings during the requested freeze period before freezing your membership")
    membership.status = "frozen"
    membership.freeze_start_date = today
    membership.freeze_until_date = until
    add_notification(
        db, membership.user_id, "Membership frozen",
        f"Your membership is frozen until {until}. Resume earlier from Membership Management; the expiry date will be adjusted for the actual pause.",
        "membership",
    )
    db.commit()
    db.refresh(membership)
    return membership


@router.post("/{membership_id}/resume", response_model=MembershipRead)
def resume_membership(
    membership_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Membership:
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    if membership.user_id != current_user.id and current_user.role not in {"admin", "staff"}:
        raise HTTPException(status_code=403, detail="You cannot resume another member's membership")
    if membership.status != "frozen" or membership.freeze_start_date is None or membership.freeze_until_date is None:
        raise HTTPException(status_code=409, detail="Membership is not currently frozen")
    today = business_today()
    effective_end = min(today, membership.freeze_until_date)
    frozen_days = max((effective_end - membership.freeze_start_date).days, 0)
    membership.expiry_date = membership.expiry_date + timedelta(days=frozen_days)
    membership.status = "active" if membership.expiry_date >= today else "expired"
    membership.freeze_start_date = None
    membership.freeze_until_date = None
    add_notification(
        db, membership.user_id, "Membership resumed",
        f"Your membership is {membership.status}. Its expiry date has been adjusted by {frozen_days} frozen day(s) to {membership.expiry_date}.",
        "membership",
    )
    db.commit()
    db.refresh(membership)
    return membership
