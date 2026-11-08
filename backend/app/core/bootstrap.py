"""First-start bootstrap for serverless deployments (AUTO_BOOTSTRAP=true).

Per cold instance: a cheap check (schema at Alembic head? demo data present?) and only then migrations / seed.
Guarded by a process lock and a Postgres advisory lock (session pooler) so concurrent cold starts don't collide.
On Supabase it also enables RLS and revokes the REST API roles on every application table.
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


def _alembic_cfg():
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return cfg


def _head() -> str:
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(_alembic_cfg()).get_current_head()


def _harden_supabase(conn) -> None:
    """Supabase exposes `public` through PostgREST; application tables must never be reachable that way."""
    if not conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'anon'")).first():
        return
    conn.execute(text("""
        DO $$ DECLARE t record; BEGIN
          FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = current_schema() LOOP
            EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t.tablename);
            EXECUTE format('REVOKE ALL ON TABLE %I FROM anon, authenticated', t.tablename);
          END LOOP;
        END $$;"""))
    conn.commit()


def ensure_bootstrapped() -> None:
    global _done
    if _done or not settings.auto_bootstrap:
        return
    with _lock:
        if _done:
            return
        from app.core.db import engine

        with engine.connect() as conn:
            version = None
            if conn.execute(text("SELECT to_regclass('alembic_version') IS NOT NULL")).scalar():
                version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            seeded = version is not None and conn.execute(text("SELECT EXISTS (SELECT 1 FROM regulatory_requirements)")).scalar()
            drafts = seeded and conn.execute(text("SELECT EXISTS (SELECT 1 FROM assessment_drafts)")).scalar()
            conn.commit()
            if version == _head() and seeded and drafts:
                _done = True  # warm path: nothing to do
                return
            if not conn.execute(text("SELECT pg_try_advisory_lock(7351001)")).scalar():
                log.info("another instance is bootstrapping")
                return
            try:
                if version != _head():
                    from alembic import command

                    log.warning("bootstrap: migrating %s -> head", version)
                    command.upgrade(_alembic_cfg(), "head")
                _harden_supabase(conn)
                from app.seed import run as seed

                if not seeded:
                    import sys

                    argv, sys.argv = sys.argv, ["seed"]
                    try:
                        seed.main()
                    finally:
                        sys.argv = argv
                elif not drafts:
                    log.warning("bootstrap: re-running demo assessments")
                    seed.seed_assessments_from_db()
                _harden_supabase(conn)
                _done = True
                log.warning("bootstrap: complete")
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(7351001)"))
                conn.commit()
