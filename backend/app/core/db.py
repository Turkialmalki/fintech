from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs() -> dict:
    if settings.serverless:
        # Serverless instances are reused between requests (Fluid compute): keep a *small* pool of session-pooler
        # connections, verified before use and recycled often. No server-side prepared statements (pooler-safe).
        return {"pool_size": 2, "max_overflow": 3, "pool_pre_ping": True, "pool_recycle": 120, "pool_timeout": 15,
                "connect_args": {"prepare_threshold": None, "connect_timeout": 10}}
    return {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}


def _resolve_url() -> str:
    """DATABASE_URL may list alternatives separated by '|' (e.g. pooler hosts); the first reachable one wins."""
    candidates = [u.strip() for u in settings.database_url.split("|") if u.strip()]
    if len(candidates) == 1:
        return candidates[0]
    last: Exception | None = None
    for url in candidates:
        try:
            probe = create_engine(url, **_engine_kwargs())
            with probe.connect() as c:
                c.execute(text("SELECT 1"))
            probe.dispose()
            return url
        except Exception as e:  # try the next candidate
            last = e
    raise RuntimeError(f"no database URL candidate is reachable: {last}")


DATABASE_URL = _resolve_url()
engine = create_engine(DATABASE_URL, future=True, **_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one transaction per request, rolled back on error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


_vector_cache: dict[str, bool] = {}


def pgvector_available(bind=None) -> bool:
    """True when the `vector` extension is installed in this database."""
    key = str((bind or engine).url)
    if key not in _vector_cache:
        with (bind or engine).connect() as conn:
            row = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname='vector'")).first()
            _vector_cache[key] = row is not None
    return _vector_cache[key]
