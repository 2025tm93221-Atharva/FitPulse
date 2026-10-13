"""Create predictable admin/staff identities for local/CI acceptance tests only.

Never run this script against staging/production databases.
"""
import os

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User

ACCOUNTS = (
    ("v1-e2e-admin@example.test", "E2E_ADMIN_PASSWORD", "V1 E2E Admin", "admin"),
    ("v1-e2e-staff@example.test", "E2E_STAFF_PASSWORD", "V1 E2E Staff", "staff"),
)


def main() -> None:
    if os.getenv("ENVIRONMENT", "development").lower() != "development":
        raise SystemExit("Refusing to seed E2E accounts outside ENVIRONMENT=development")
    with SessionLocal() as db:
        for email, password_env, full_name, role in ACCOUNTS:
            password = os.getenv(password_env)
            if not password or len(password) < 12:
                raise SystemExit(f"Set {password_env} to a test-only password of at least 12 characters")
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, full_name=full_name, hashed_password=hash_password(password), role=role, is_active=True)
                db.add(user)
            else:
                user.full_name = full_name
                user.hashed_password = hash_password(password)
                user.role = role
                user.is_active = True
        db.commit()


if __name__ == "__main__":
    main()
