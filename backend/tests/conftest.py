"""Test fixtures: a dedicated PostgreSQL database, migrated with Alembic and seeded with the demo data."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://rip:rip@localhost:5432/rip_test")
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("STORAGE_DIR", str(ROOT / ".test-storage"))
os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["MCP_RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["LOG_LEVEL"] = "WARNING"
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

PASSWORD = "Demo@2026!"


@pytest.fixture(scope="session", autouse=True)
def database():
    from app.core.db import engine

    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(cfg, "head")
    from app.seed import run as seed

    sys.argv = ["seed"]
    seed.main()
    yield


@pytest.fixture(scope="session")
def client():
    from app.main import app

    return TestClient(app)


def _login(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def h(client):
    """Auth headers per role."""
    return {role: _login(client, f"{role}@rip.demo") for role in ("admin", "supervisor", "analyst", "auditor", "viewer")} | {
        "tenant_b": _login(client, "admin@tenantb.demo")}


@pytest.fixture()
def principal():
    from app.api.deps import principal_from_user
    from app.core.db import session_scope
    from app.models import User

    def make(email="analyst@rip.demo"):
        with session_scope() as db:
            return principal_from_user(db.scalar(select(User).where(User.email == email)))

    return make


def app_id_by_name(client, headers, name):
    r = client.get("/api/v1/applications", params={"q": name}, headers=headers)
    return r.json()["items"][0]["id"]
