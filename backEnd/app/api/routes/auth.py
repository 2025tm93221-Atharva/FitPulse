from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.mailer import send_password_reset_email
from app.core.notifications import add_notification
from app.core.security import create_access_token, hash_password, verify_password
from app.models import PasswordResetToken, User
from app.schemas import (
    LoginRequest, PasswordResetConfirm, PasswordResetRequest, PasswordResetRequestResponse,
    RegisterRequest, TokenResponse, UserRead,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    normalized_email = str(payload.email).strip().lower()
    existing = db.scalar(select(User.id).where(User.email == normalized_email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        email=normalized_email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role="member",
        is_active=True,
    )
    db.add(user)
    db.flush()
    add_notification(db, user.id, "Welcome to FIT PULSE", "Your member account is ready. Contact your club if a membership needs to be assigned.", "account")
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    normalized_email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    # Return the same response for an unknown email and a bad password to reduce account enumeration.
    if user is None or not verify_password(payload.password, user.hashed_password) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_at = create_access_token(user.id, user.token_version)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(access_token=token, expires_at=expires_at, user=user)


@router.post("/password-reset/request", response_model=PasswordResetRequestResponse, status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    payload: PasswordResetRequest, response: Response, db: Session = Depends(get_db)
) -> PasswordResetRequestResponse:
    """Request a password reset without revealing whether an email is registered."""
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    normalized_email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email, User.is_active.is_(True)))
    debug_token: str | None = None
    if user is not None:
        now = datetime.now(timezone.utc)
        # Invalidate older outstanding links; only the newest request remains usable.
        pending = list(db.scalars(select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
        )))
        for old_token in pending:
            old_token.used_at = now
        token = secrets.token_urlsafe(32)
        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=_token_digest(token),
            expires_at=now + timedelta(minutes=settings.password_reset_token_expire_minutes),
        )
        db.add(reset_record)
        db.commit()
        try:
            send_password_reset_email(user.email, token)
        except Exception:
            # Do not expose mail errors or account existence to the caller. Invalidate the
            # un-delivered token and let operational logs/alerts surface the provider failure.
            logger.exception("Password reset email delivery failed")
            reset_record.used_at = datetime.now(timezone.utc)
            db.commit()
        if settings.environment.lower() == "development":
            debug_token = token
    return PasswordResetRequestResponse(
        message="If an active account exists for this email, password-reset instructions will be sent.",
        debug_reset_token=debug_token,
    )


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(
    payload: PasswordResetConfirm, response: Response, db: Session = Depends(get_db)
) -> None:
    """Consume a reset token once, update the password, and revoke existing JWT sessions."""
    response.headers["Cache-Control"] = "no-store, private"
    reset_record = db.scalar(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == _token_digest(payload.token)
    ))
    now = datetime.now(timezone.utc)
    if (reset_record is None or reset_record.used_at is not None
            or _aware_utc(reset_record.expires_at) <= now):
        raise HTTPException(status_code=400, detail="Password reset link is invalid or expired")
    user = db.get(User, reset_record.user_id)
    if user is None or not user.is_active:
        reset_record.used_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="Password reset link is invalid or expired")

    user.hashed_password = hash_password(payload.new_password)
    user.token_version += 1
    reset_record.used_at = now
    # Invalidate every sibling link for this account after a successful reset.
    other_tokens = db.scalars(select(PasswordResetToken).where(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != reset_record.id,
        PasswordResetToken.used_at.is_(None),
    ))
    for item in other_tokens:
        item.used_at = now
    add_notification(db, user.id, "Password changed", "Your account password was changed. If this was not you, contact support immediately.", "security")
    db.commit()
