from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Membership, User
from app.schemas import MembershipCreate, MembershipRead, MembershipStatusUpdate

router = APIRouter(prefix="/memberships", tags=["memberships"])
ALLOWED_TRANSITIONS = {
    "pending": {"active", "cancelled"},
    "active": {"frozen", "cancelled", "expired"},
    "frozen": {"active", "cancelled", "expired"},
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
        today = date.today()
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
    db.commit()
    db.refresh(membership)
    return membership


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



