"""Deployment entrypoint. If the application fails to import (e.g. misconfiguration on a serverless
platform), serve a minimal diagnostics app instead of an opaque crash. No secret values are exposed."""
from __future__ import annotations

import os
import re
import traceback

from fastapi import FastAPI


def _build() -> FastAPI:
    try:
        from app.main import app as real_app

        return real_app
    except Exception as exc:  # pragma: no cover - only on broken deployments
        err = re.sub(r"://[^@\s]+@", "://***@", f"{type(exc).__name__}: {exc}")[:500]
        where = [ln.strip() for ln in traceback.format_exc().splitlines() if ln.strip().startswith("File")][-3:]
        fallback = FastAPI(title="RIP — startup failure")

        @fallback.get("/{path:path}")
        def diagnostics(path: str):
            return {"status": "startup_failed", "error": err, "where": where,
                    "env_present": {k: bool(os.getenv(k)) for k in ("DATABASE_URL", "POSTGRES_URL", "SUPABASE_JWT_SECRET", "JWT_SECRET", "VERCEL")}}

        return fallback


app = _build()
