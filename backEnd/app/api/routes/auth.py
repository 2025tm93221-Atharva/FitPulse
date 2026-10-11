from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["authentication"])


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
    token, expires_at = create_access_token(user.id)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(access_token=token, expires_at=expires_at, user=user)
