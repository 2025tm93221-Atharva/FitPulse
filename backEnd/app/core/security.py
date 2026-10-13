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


def create_access_token(user_id: int, token_version: int = 0) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "token_version": token_version,
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


# Scanner keys are high-entropy opaque credentials. Only a SHA-256 digest of the
# secret is stored; unlike human passwords, random scanner secrets are not guessable.
def generate_scanner_api_key() -> tuple[str, str, str]:
    import hashlib
    import secrets

    key_id = secrets.token_hex(8)
    secret = secrets.token_urlsafe(32)
    raw_key = f"fscan_{key_id}.{secret}"
    key_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return key_id, raw_key, key_hash


def parse_scanner_api_key(raw_key: str) -> tuple[str, str] | None:
    if not raw_key or not raw_key.startswith("fscan_"):
        return None
    key_id, separator, secret = raw_key[6:].partition(".")
    if not separator or len(key_id) != 16 or len(secret) < 32:
        return None
    if not all(char in "0123456789abcdef" for char in key_id.lower()):
        return None
    return key_id, secret


def hash_scanner_secret(secret: str) -> str:
    import hashlib

    return hashlib.sha256(secret.encode("utf-8")).hexdigest()
