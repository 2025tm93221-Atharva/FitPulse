from collections.abc import Callable
import hmac
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token, hash_scanner_secret, parse_scanner_api_key
from app.models import ScannerDevice, User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("token_type") != "access":
            raise unauthorized
        user_id = int(payload["sub"])
        token_version = int(payload.get("token_version", 0))
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise unauthorized

    user = db.get(User, user_id)
    if user is None or not user.is_active or user.token_version != token_version:
        raise unauthorized
    return user


def require_roles(*allowed_roles: str) -> Callable:
    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return role_dependency


def get_current_scanner(
    x_scanner_key: Annotated[str | None, Header(alias="X-Scanner-Key")] = None,
    db: Session = Depends(get_db),
) -> ScannerDevice:
    unauthorized = HTTPException(status_code=401, detail="Invalid or inactive scanner credentials")
    parsed = parse_scanner_api_key(x_scanner_key or "")
    if parsed is None:
        raise unauthorized
    key_id, secret = parsed
    device = db.scalar(select(ScannerDevice).where(ScannerDevice.key_id == key_id))
    if device is None or not device.is_active:
        raise unauthorized
    if not hmac.compare_digest(device.key_hash, hash_scanner_secret(secret)):
        raise unauthorized
    return device
