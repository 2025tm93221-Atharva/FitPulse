import sys

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app import cli
from app.core.security import verify_password
from app.models import ScannerDevice, User

PASSWORD = "OperatorPassphrase!2026"


@pytest.fixture()
def run_cli(db_engine, monkeypatch):
    monkeypatch.setattr(cli, "SessionLocal", sessionmaker(bind=db_engine, expire_on_commit=False))
    monkeypatch.setattr(cli, "getpass", lambda _prompt: PASSWORD)

    def run(*args: str) -> None:
        monkeypatch.setattr(sys, "argv", ["cli", *args])
        cli.main()

    return run


@pytest.mark.parametrize("role", ["admin", "staff"])
def test_create_privileged_user(run_cli, db_session, role):
    run_cli(f"create-{role}", "--email", " Ops@Example.com ", "--full-name", "Ops")
    user = db_session.scalar(select(User).where(User.email == "ops@example.com"))
    assert user.role == role
    assert verify_password(PASSWORD, user.hashed_password)
    with pytest.raises(SystemExit, match="already exists"):
        run_cli(f"create-{role}", "--email", "ops@example.com", "--full-name", "Ops")


def test_set_password(run_cli, db_session, member_account):
    run_cli("set-password", "--email", "member@example.com")
    user = db_session.scalar(select(User).where(User.email == "member@example.com"))
    assert verify_password(PASSWORD, user.hashed_password)
    with pytest.raises(SystemExit, match="not found"):
        run_cli("set-password", "--email", "nobody@example.com")


def test_password_rules(monkeypatch):
    monkeypatch.setattr(cli, "getpass", lambda _prompt: "short")
    with pytest.raises(SystemExit, match="between 12 and 128"):
        cli.read_new_password()
    answers = iter([PASSWORD, PASSWORD + "x"])
    monkeypatch.setattr(cli, "getpass", lambda _prompt: next(answers))
    with pytest.raises(SystemExit, match="do not match"):
        cli.read_new_password()


def test_scanner_lifecycle(run_cli, db_session, client, capsys):
    run_cli("create-scanner", "--name", "Door", "--location-name", "Downtown")
    first_key = capsys.readouterr().out.strip().splitlines()[-1]
    scanner = db_session.scalar(select(ScannerDevice))

    def whoami(key: str) -> int:
        return client.get("/api/scanner/check-ins/whoami", headers={"X-Scanner-Key": key}).status_code

    assert whoami(first_key) == 200
    run_cli("rotate-scanner-key", "--scanner-id", str(scanner.id))
    second_key = capsys.readouterr().out.strip().splitlines()[-1]
    assert (whoami(first_key), whoami(second_key)) == (401, 200)
    run_cli("deactivate-scanner", "--scanner-id", str(scanner.id))
    assert whoami(second_key) == 401


def test_scanner_errors(run_cli):
    with pytest.raises(SystemExit, match="must not be blank"):
        run_cli("create-scanner", "--name", " ", "--location-name", "Downtown")
    for command in ("rotate-scanner-key", "deactivate-scanner"):
        with pytest.raises(SystemExit, match="Scanner not found"):
            run_cli(command, "--scanner-id", "404")
