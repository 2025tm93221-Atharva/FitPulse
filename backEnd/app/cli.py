"""Operational commands. Run after applying migrations."""
import argparse
from getpass import getpass

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import generate_scanner_api_key, hash_password
from app.models import ScannerDevice, User


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



def create_scanner(name: str, location_name: str) -> None:
    key_id, raw_key, key_hash = generate_scanner_api_key()
    with SessionLocal() as db:
        device = ScannerDevice(
            name=name.strip(),
            location_name=location_name.strip(),
            key_id=key_id,
            key_hash=key_hash,
            is_active=True,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        print(f"Created scanner #{device.id}: {device.name} at {device.location_name}")
        print("Copy this scanner key now; it will not be displayed again:")
        print(raw_key)


def rotate_scanner_key(scanner_id: int) -> None:
    key_id, raw_key, key_hash = generate_scanner_api_key()
    with SessionLocal() as db:
        device = db.get(ScannerDevice, scanner_id)
        if device is None:
            raise SystemExit("Scanner not found")
        device.key_id = key_id
        device.key_hash = key_hash
        db.commit()
        print(f"Rotated key for scanner #{device.id}: {device.name}")
        print("Copy this scanner key now; the previous key is invalid:")
        print(raw_key)


def deactivate_scanner(scanner_id: int) -> None:
    with SessionLocal() as db:
        device = db.get(ScannerDevice, scanner_id)
        if device is None:
            raise SystemExit("Scanner not found")
        device.is_active = False
        db.commit()
        print(f"Deactivated scanner #{device.id}: {device.name}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Fitness Membership API operations")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for role in ("admin", "staff"):
        sub = subparsers.add_parser(f"create-{role}", help=f"Create a {role} account")
        sub.add_argument("--email", required=True)
        sub.add_argument("--full-name", required=True)
    reset_parser = subparsers.add_parser("set-password", help="Set/reset a user's password locally")
    reset_parser.add_argument("--email", required=True)
    scanner_parser = subparsers.add_parser("create-scanner", help="Register a trusted physical scanner")
    scanner_parser.add_argument("--name", required=True)
    scanner_parser.add_argument("--location-name", required=True)
    rotate_parser = subparsers.add_parser("rotate-scanner-key", help="Rotate a scanner's API key")
    rotate_parser.add_argument("--scanner-id", type=int, required=True)
    deactivate_parser = subparsers.add_parser("deactivate-scanner", help="Disable a scanner immediately")
    deactivate_parser.add_argument("--scanner-id", type=int, required=True)

    args = parser.parse_args()
    if args.command == "create-admin":
        create_privileged_user(args.email, args.full_name, "admin")
    elif args.command == "create-staff":
        create_privileged_user(args.email, args.full_name, "staff")
    elif args.command == "set-password":
        set_password(args.email)
    elif args.command == "create-scanner":
        if not args.name.strip() or not args.location_name.strip():
            raise SystemExit("Scanner name and location must not be blank")
        create_scanner(args.name, args.location_name)
    elif args.command == "rotate-scanner-key":
        rotate_scanner_key(args.scanner_id)
    elif args.command == "deactivate-scanner":
        deactivate_scanner(args.scanner_id)


if __name__ == "__main__":
    main()
