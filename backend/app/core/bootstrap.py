"""First-start bootstrap for serverless deployments (AUTO_BOOTSTRAP=true).

Runs Alembic migrations and, if the database has no demo data yet, the synthetic demo seed
(including real agent runs). Guarded by a process lock and a Postgres advisory lock so that
concurrent cold starts do not run it twice.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings

log = logging.getLogger("rip.bootstrap")
_lock = threading.Lock()
_done = False
BACKEND = Path(__file__).resolve().parents[2]


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")


def ensure_bootstrapped() -> None:
    global _done
    if _done or not settings.auto_bootstrap:
        return
    with _lock:
        if _done:
            return
        from app.core.db import engine

        with engine.connect() as conn:
            # The `rip` schema keeps app tables out of Supabase's auto-exposed `public` schema.
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS rip"))
            conn.commit()
            got = conn.execute(text("SELECT pg_try_advisory_lock(7351001)")).scalar()
            if not got:
                log.info("another instance is bootstrapping")
                return
            try:
                has_table = conn.execute(text("SELECT to_regclass('regulatory_requirements') IS NOT NULL")).scalar()
                seeded = has_table and conn.execute(text("SELECT EXISTS (SELECT 1 FROM regulatory_requirements)")).scalar()
                conn.commit()
                log.warning("bootstrap: migrating (seeded=%s)", seeded)
                _migrate()
                if not seeded:
                    import sys

                    from app.seed import run as seed

                    argv, sys.argv = sys.argv, ["seed"]
                    try:
                        seed.main()
                    finally:
                        sys.argv = argv
                _done = True
                log.warning("bootstrap: complete")
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(7351001)"))
                conn.commit()
