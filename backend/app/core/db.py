from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=20, future=True)
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
