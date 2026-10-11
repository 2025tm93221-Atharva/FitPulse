from datetime import date

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.security import create_checkin_token, decode_token
from app.models import CheckIn, Membership, User
from app.schemas import CheckInRead, CheckInValidateRequest, QRTokenResponse

router = APIRouter(prefix="/check-ins", tags=["check-ins"])


def _eligible_membership(db: Session, user_id: int) -> Membership | None:
    today = date.today()  # Membership dates are evaluated in the club's configured business timezone in production.
    return db.scalar(select(Membership).where(
        Membership.user_id == user_id,
        Membership.status == "active",
        Membership.start_date <= today,
        Membership.expiry_date >= today,
    ).order_by(Membership.expiry_date.desc()).limit(1))


@router.post("/qr-token", response_model=QRTokenResponse)
def issue_qr_token(
    response: Response,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> QRTokenResponse:
    if current_user.role != "member":
        raise HTTPException(status_code=403, detail="Only member accounts can request a member pass")
    membership = _eligible_membership(db, current_user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail="No eligible active membership was found")
    token, _, expires_at = create_checkin_token(current_user.id, membership.id)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    return QRTokenResponse(qr_token=token, membership_id=membership.id, expires_at=expires_at)


@router.post("/validate", response_model=CheckInRead, status_code=status.HTTP_201_CREATED)
def validate_qr_and_check_in(
    payload: CheckInValidateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("staff", "admin")),
) -> CheckIn:
    try:
        claims = decode_token(payload.qr_token)
        if claims.get("token_type") != "gym_checkin":
            raise ValueError("Wrong token purpose")
        user_id = int(claims["sub"])
        membership_id = int(claims["membership_id"])
        jti = str(claims["jti"])
        if not jti or len(jti) > 64:
            raise ValueError("Invalid token ID")
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired gym pass")

    member = db.get(User, user_id)
    if member is None or not member.is_active:
        raise HTTPException(status_code=403, detail="Member account is inactive")
    membership = db.get(Membership, membership_id)
    if membership is None or membership.user_id != user_id:
        raise HTTPException(status_code=403, detail="Gym pass is not associated with a valid membership")
    today = date.today()
    if not (membership.status == "active" and membership.start_date <= today <= membership.expiry_date):
        raise HTTPException(status_code=403, detail="Membership is not eligible for entry")
    if db.scalar(select(CheckIn.id).where(CheckIn.qr_jti == jti)) is not None:
        raise HTTPException(status_code=409, detail="This gym pass has already been used")

    checkin = CheckIn(
        user_id=user_id,
        membership_id=membership_id,
        location_name=payload.location_name,
        result="accepted",
        qr_jti=jti,
    )
    db.add(checkin)
    try:
        db.commit()
        db.refresh(checkin)
    except IntegrityError as exc:  # A unique constraint also protects against concurrent replay.
        db.rollback()
        raise HTTPException(status_code=409, detail="This gym pass has already been used") from exc
    return checkin


@router.get("/me", response_model=list[CheckInRead])
def my_check_in_history(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[CheckIn]:
    return list(db.scalars(select(CheckIn).where(CheckIn.user_id == current_user.id)
                           .order_by(CheckIn.checked_in_at.desc()).limit(100)))
