"""Every release must be able to migrate a blank database and match the ORM."""
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def alembic(database_url: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND, env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True, text=True,
    )


def test_fresh_database_migrates_and_matches_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    upgraded = alembic(url, "upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr
    drift = alembic(url, "check")
    assert drift.returncode == 0, drift.stdout + drift.stderr
