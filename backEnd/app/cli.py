"""Operational commands. Run after applying migrations."""
import argparse
from getpass import getpass

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User


def read_new_password(label: str = "Password") -> str:
    password = getpass(f"{label} (12+ characters): ")
    confirm = getpass("Confirm password: ")
    if len(password) < 12 or len(password) > 128:
        raise SystemExit("Password must be between 12 and 128 characters")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    return password


def create_privileged_user(email: str, full_name: str, role: str) -> None:
    normalized_email = email.strip().lower()
    password = read_new_password(f"{role.title()} password")
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == normalized_email)) is not None:
            raise SystemExit("An account with this email already exists")
        user = User(
            email=normalized_email,
            full_name=full_name.strip(),
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Created {role} account: {normalized_email}")


def set_password(email: str) -> None:
    normalized_email = email.strip().lower()
    password = read_new_password("New password")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == normalized_email))
        if user is None:
            raise SystemExit("Account not found")
        user.hashed_password = hash_password(password)
        db.commit()
        print(f"Updated password for: {normalized_email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fitness Membership API operations")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for role in ("admin", "staff"):
        sub = subparsers.add_parser(f"create-{role}", help=f"Create a {role} account")
        sub.add_argument("--email", required=True)
        sub.add_argument("--full-name", required=True)
    reset_parser = subparsers.add_parser("set-password", help="Set/reset a user's password locally")
    reset_parser.add_argument("--email", required=True)

    args = parser.parse_args()
    if args.command == "create-admin":
        create_privileged_user(args.email, args.full_name, "admin")
    elif args.command == "create-staff":
        create_privileged_user(args.email, args.full_name, "staff")
    elif args.command == "set-password":
        set_password(args.email)


if __name__ == "__main__":
    main()
