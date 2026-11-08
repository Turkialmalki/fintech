"""Deployment entrypoint. If the application fails to import (e.g. misconfiguration on a serverless
platform), serve a minimal diagnostics app instead of an opaque crash. No secret values are exposed."""
from __future__ import annotations

import os
import re
import traceback

try:
    from app.main import app  # noqa: F401
except Exception as exc:  # pragma: no cover - only on broken deployments
    from fastapi import FastAPI

    _err = re.sub(r"://[^@\s]+@", "://***@", f"{type(exc).__name__}: {exc}")[:500]
    _where = [ln.strip() for ln in traceback.format_exc().splitlines() if ln.strip().startswith("File")][-3:]
    app = FastAPI(title="RIP — startup failure")

    @app.get("/{path:path}")
    def diagnostics(path: str):
        return {"status": "startup_failed", "error": _err, "where": _where,
                "env_present": {k: bool(os.getenv(k)) for k in ("DATABASE_URL", "POSTGRES_URL", "SUPABASE_JWT_SECRET", "JWT_SECRET", "VERCEL")}}
