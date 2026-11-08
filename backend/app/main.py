from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from app.api.v1 import applications, assessments, auth, platform, readiness, regulatory
from app.core.config import settings
from app.core.db import engine, session_scope
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.ratelimit import limiter
from app.models import RequestMetric

configure_logging()
log = logging.getLogger("rip.api")

app = FastAPI(
    title="RIP — Saudi Fintech Regulatory Intelligence Platform API",
    description="Regulatory readiness and assessment API. "
                "AI output is decision support only; consequential decisions require a human user.",
    version="1.0.0",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
)
install_error_handlers(app)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
                   expose_headers=["X-Request-ID", "Content-Disposition"])

SKIP_METRICS = {"/healthz", "/readyz", "/metrics"}


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = rid[:64]
    path = request.url.path
    if settings.auto_bootstrap and path.startswith(settings.api_prefix) and not path.endswith("/system/diagnostics"):
        from starlette.concurrency import run_in_threadpool

        from app.core.bootstrap import ensure_bootstrapped

        await run_in_threadpool(ensure_bootstrapped)
    if path.startswith(settings.api_prefix) and request.method != "OPTIONS":
        auth = request.headers.get("authorization", "")
        ident = auth[-24:] if auth else (request.client.host if request.client else "anon")
        if not limiter.hit(f"api:{ident}", settings.rate_limit_per_minute):
            return JSONResponse(status_code=429, headers={"Retry-After": "60", "X-Request-ID": rid},
                                content={"error": {"code": "RATE_LIMITED", "message": "Too many requests",
                                                   "message_ar": "عدد الطلبات تجاوز الحد المسموح", "details": {}, "request_id": rid}})
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - t0) * 1000
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers.setdefault("Cache-Control", "no-store")
    if path.startswith(settings.api_prefix) and path not in SKIP_METRICS:
        route = request.scope.get("route")
        try:
            with session_scope() as db:
                db.add(RequestMetric(id=uuid.uuid4(), created_at=datetime.now(timezone.utc), method=request.method,
                                     route=getattr(route, "path", path)[:200], status_code=response.status_code, latency_ms=elapsed))
        except Exception:
            log.exception("failed to persist request metric")
    log.info("request", extra={"request_id": rid, "method": request.method, "path": path, "status": response.status_code,
                               "latency_ms": round(elapsed, 1)})
    return response


api = APIRouter(prefix=settings.api_prefix)
for r in (auth.router, applications.router, regulatory.router, assessments.router, platform.router, readiness.router):
    api.include_router(r)
app.include_router(api)


@app.get("/healthz", tags=["health"])
def liveness():
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
def readiness():
    checks = {}
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
            checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"
    checks["redis"] = "ok" if limiter.healthy() else "degraded (in-process rate limiting)"
    ok = checks["database"] == "ok"
    return JSONResponse(status_code=200 if ok else 503, content={"status": "ready" if ok else "not_ready", "checks": checks})


@app.get("/metrics", tags=["health"], response_class=PlainTextResponse)
def prometheus():
    """Minimal Prometheus exposition from persisted request metrics (last 5 minutes)."""
    with engine.connect() as c:
        rows = c.execute(text("SELECT route, status_code, count(*), avg(latency_ms) FROM request_metrics "
                              "WHERE created_at > now() - interval '5 minutes' GROUP BY route, status_code")).all()
    lines = ["# TYPE rip_http_requests_5m gauge", "# TYPE rip_http_latency_ms_avg_5m gauge"]
    for route, code, n, avg in rows:
        lines.append(f'rip_http_requests_5m{{route="{route}",status="{code}"}} {n}')
        lines.append(f'rip_http_latency_ms_avg_5m{{route="{route}",status="{code}"}} {float(avg):.2f}')
    return "\n".join(lines) + "\n"
