from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

password_hash = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "token_type": "access",
        "iat": now,
        "exp": expires_at,
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), expires_at


def create_checkin_token(user_id: int, membership_id: int) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.qr_token_expire_seconds)
    jti = uuid4().hex
    payload = {
        "sub": str(user_id),
        "membership_id": membership_id,
        "token_type": "gym_checkin",
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token, jti, expires_at


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
