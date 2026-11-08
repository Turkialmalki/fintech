"""MCP management, AI governance, model configuration, audit, dashboard and observability APIs."""
from __future__ import annotations

import asyncio
import statistics
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.ai.service import get_ai, reset_ai_cache, resolve_config
from app.api.deps import principal_from_user, require
from app.core.config import settings
from app.core.db import get_db, pgvector_available
from app.core.errors import AppError, NotFound
from app.core.ratelimit import limiter
from app.core.security import Principal, generate_api_key
from app.models import (
    AgentRun,
    AIModel,
    AIUseCase,
    AnalystReview,
    ApplicationStatus as S,
    AssessmentCitation,
    AssessmentDraft,
    AssessmentFinding,
    AuditLog,
    FintechApplication,
    GovernanceControl,
    McpApiKey,
    ModelEvaluation,
    ModelInvocation,
    RegulatoryDocument,
    RequestMetric,
    SystemSetting,
    User,
)
from app.rag.evaluate import run_evaluation
from app.schemas.common import AIConfigIn, McpKeyIn, ModelIn, ModelPatch, UseCaseIn, UseCasePatch
from app.services import audit
from app.services.tools import TOOLS

router = APIRouter()


def _row(obj, exclude: tuple = ()) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns if c.name not in exclude}


# ================================================================ MCP
@router.get("/mcp/health", tags=["mcp"])
def mcp_health(p: Principal = Depends(require("applications:read"))):
    import httpx

    remote = {"url": settings.mcp_url, "reachable": False}
    try:
        r = httpx.get(settings.mcp_url.rsplit("/mcp", 1)[0] + "/healthz", timeout=1.5)
        remote["reachable"] = r.status_code == 200
        remote["detail"] = r.json() if r.status_code == 200 else r.text[:100]
    except Exception as e:
        remote["detail"] = f"not reachable: {type(e).__name__}"
    return {"tools": len(TOOLS), "agent_transport": settings.agent_tool_transport, "standalone_server": remote,
            "sdk": "mcp (official Python SDK) " + __import__("mcp").__version__ if hasattr(__import__("mcp"), "__version__") else "mcp"}


@router.get("/mcp/tools", tags=["mcp"])
def mcp_tools(p: Principal = Depends(require("applications:read"))):
    return [{"name": t.name, "description": t.description, "permission": t.permission, "write": t.write,
             "input_schema": t.input_model.model_json_schema(), "allowed_for_you": p.has(t.permission)} for t in TOOLS.values()]


@router.post("/mcp/tools/{name}/test", tags=["mcp"])
def mcp_test(name: str, args: dict, p: Principal = Depends(require("applications:read"))):
    """Invoke a READ-ONLY tool through a real in-process MCP session as the current user."""
    from mcp import Client

    from rip_mcp.server import build_server

    spec = TOOLS.get(name)
    if spec is None:
        raise NotFound("Tool", "الأداة")
    if spec.write:
        raise AppError("Write tools cannot be run from the console", "لا يمكن تشغيل أدوات الكتابة من وحدة الاختبار", status_code=403)
    tester = Principal(user_id=p.user_id, org_id=p.org_id, email=p.email, roles=p.roles, permissions=p.permissions,
                       actor_type="MCP_CLIENT", scopes=frozenset({"read"}))

    async def go():
        async with Client(build_server(default_principal=tester, transport_label="mcp_console")) as c:
            r = await c.call_tool(name, args)
            return r.structured_content

    t0 = datetime.now(timezone.utc)
    result = asyncio.run(go())
    return {"result": result, "duration_ms": int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)}


@router.get("/mcp/executions", tags=["mcp"])
def mcp_execs(p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db), limit: int = Query(50, le=200)):
    rows = db.scalars(select(AuditLog).where(AuditLog.org_id == p.org_id, AuditLog.category == "MCP")
                      .order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [{"id": str(a.id), "tool": a.resource_id, "action": a.action, "outcome": a.outcome, "actor_type": a.actor_type,
             "transport": a.details.get("transport"), "duration_ms": a.details.get("duration_ms"), "run_id": a.details.get("run_id"),
             "error": a.details.get("error"), "created_at": a.created_at} for a in rows]


@router.get("/mcp/keys", tags=["mcp"])
def list_keys(p: Principal = Depends(require("mcp:manage")), db: Session = Depends(get_db)):
    rows = db.scalars(select(McpApiKey).where(McpApiKey.org_id == p.org_id).order_by(McpApiKey.created_at.desc())).all()
    return [{"id": str(k.id), "name": k.name, "key_prefix": k.key_prefix, "scopes": k.scopes, "created_at": k.created_at,
             "revoked_at": k.revoked_at, "last_used_at": k.last_used_at, "user_email": k.user.email} for k in rows]


@router.post("/mcp/keys", status_code=201, tags=["mcp"])
def create_key(body: McpKeyIn, p: Principal = Depends(require("mcp:manage")), db: Session = Depends(get_db)):
    bad = [s for s in body.scopes if s not in ("read", "write")]
    if bad or "read" not in body.scopes:
        raise AppError("Scopes must include 'read' and may include 'write'", "يجب أن تتضمن الصلاحيات القراءة", status_code=422)
    raw, prefix, h = generate_api_key()
    k = McpApiKey(org_id=p.org_id, name=body.name, key_prefix=prefix, key_hash=h, user_id=p.user_id, scopes=sorted(set(body.scopes)))
    db.add(k)
    db.flush()
    audit.record(db, category="MCP", action="api_key_created", principal=p, resource_type="mcp_api_key", resource_id=k.id,
                 details={"scopes": k.scopes, "name": body.name})
    return {"id": str(k.id), "api_key": raw, "key_prefix": prefix, "scopes": k.scopes,
            "notice": "Store this key now; it cannot be shown again."}


@router.delete("/mcp/keys/{key_id}", status_code=204, tags=["mcp"])
def revoke_key(key_id: uuid.UUID, p: Principal = Depends(require("mcp:manage")), db: Session = Depends(get_db)):
    k = db.get(McpApiKey, key_id)
    if not k or k.org_id != p.org_id:
        raise NotFound("Key", "المفتاح")
    k.revoked_at = datetime.now(timezone.utc)
    audit.record(db, category="MCP", action="api_key_revoked", principal=p, resource_type="mcp_api_key", resource_id=k.id)


# ================================================================ AI configuration
@router.get("/ai/config", tags=["ai"])
def ai_config(p: Principal = Depends(require("governance:read"))):
    ai = get_ai()
    providers = {}
    for name in ("qwen", "llama", "openai_compatible"):
        cfg = resolve_config({"provider": name})
        providers[name] = {"base_url_configured": bool(cfg.base_url), "api_key_configured": bool(cfg.api_key), "default_model": cfg.model}
    return {"active": {**ai.cfg.public(), "is_mock": ai.is_mock, "capabilities": ai.llm.capabilities.to_dict()},
            "embedding": {"provider": ai.embedder.name, "model": ai.embedder.model, "dim": ai.embedder.dim, "is_mock": ai.embedder.is_mock},
            "providers": providers, "vector_backend": "pgvector" if pgvector_available() else "array",
            "temperature": settings.ai_temperature, "max_tokens": settings.ai_max_tokens}


@router.put("/ai/config", tags=["ai"])
def set_ai_config(body: AIConfigIn, p: Principal = Depends(require("governance:manage")), db: Session = Depends(get_db)):
    cfg = resolve_config(body.model_dump())
    if body.provider != "mock" and not cfg.base_url:
        raise AppError(f"{body.provider.upper()}_BASE_URL (or AI_BASE_URL) is not configured on the server",
                       f"لم يتم ضبط {body.provider.upper()}_BASE_URL على الخادم", status_code=422, code="PROVIDER_NOT_CONFIGURED")
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == "ai.active_provider", SystemSetting.org_id.is_(None)))
    if row is None:
        row = SystemSetting(key="ai.active_provider", org_id=None, description="Runtime model selection (no secrets)")
        db.add(row)
    row.value = body.model_dump()
    reset_ai_cache()
    audit.record(db, category="SETTINGS", action="ai_provider_switched", principal=p, details=body.model_dump())
    return {"active": cfg.public()}


@router.post("/ai/probe", tags=["ai"])
def probe(p: Principal = Depends(require("governance:manage")), db: Session = Depends(get_db)):
    ai = get_ai()
    caps = ai.llm.probe()
    m = db.scalar(select(AIModel).where(AIModel.org_id == p.org_id, AIModel.provider == ai.cfg.provider, AIModel.model_id == ai.llm.model))
    if m:
        m.capabilities = caps.to_dict()
        m.capabilities_checked_at = datetime.now(timezone.utc)
    audit.record(db, category="MODEL", action="capabilities_probed", principal=p, details={"provider": ai.cfg.provider, **caps.to_dict()})
    return {"provider": ai.cfg.provider, "model": ai.llm.model, "capabilities": caps.to_dict()}


# ================================================================ governance
@router.get("/governance/models", tags=["governance"])
def models(p: Principal = Depends(require("governance:read")), db: Session = Depends(get_db)):
    return [_row(m) for m in db.scalars(select(AIModel).where(AIModel.org_id == p.org_id, AIModel.deleted_at.is_(None)).order_by(AIModel.created_at))]


@router.post("/governance/models", status_code=201, tags=["governance"])
def add_model(body: ModelIn, p: Principal = Depends(require("governance:manage")), db: Session = Depends(get_db)):
    m = AIModel(org_id=p.org_id, **body.model_dump())
    db.add(m)
    db.flush()
    audit.record(db, category="GOVERNANCE", action="model_registered", principal=p, resource_type="ai_model", resource_id=m.id,
                 details={"provider": m.provider, "model": m.model_id})
    return _row(m)


@router.patch("/governance/models/{mid}", tags=["governance"])
def patch_model(mid: uuid.UUID, body: ModelPatch, p: Principal = Depends(require("governance:manage")), db: Session = Depends(get_db)):
    m = db.get(AIModel, mid)
    if not m or m.org_id != p.org_id:
        raise NotFound("Model", "النموذج")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(m, k, v)
    audit.record(db, category="GOVERNANCE", action="model_updated", principal=p, resource_type="ai_model", resource_id=m.id,
                 details=body.model_dump(exclude_none=True))
    return _row(m)


@router.get("/governance/use-cases", tags=["governance"])
def use_cases(p: Principal = Depends(require("governance:read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(AIUseCase).where(AIUseCase.org_id == p.org_id, AIUseCase.deleted_at.is_(None)).order_by(AIUseCase.code)).all()
    return [{**_row(u), "model_name": u.model.name if u.model else None} for u in rows]


@router.post("/governance/use-cases", status_code=201, tags=["governance"])
def add_use_case(body: UseCaseIn, p: Principal = Depends(require("governance:manage")), db: Session = Depends(get_db)):
    u = AIUseCase(org_id=p.org_id, **body.model_dump())
    db.add(u)
    db.flush()
    audit.record(db, category="GOVERNANCE", action="use_case_registered", principal=p, resource_type="ai_use_case", resource_id=u.id)
    return _row(u)


@router.patch("/governance/use-cases/{uid}", tags=["governance"])
def patch_use_case(uid: uuid.UUID, body: UseCasePatch, p: Principal = Depends(require("governance:manage")), db: Session = Depends(get_db)):
    u = db.get(AIUseCase, uid)
    if not u or u.org_id != p.org_id:
        raise NotFound("Use case", "حالة الاستخدام")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(u, k, v)
    audit.record(db, category="GOVERNANCE", action="use_case_updated", principal=p, resource_type="ai_use_case", resource_id=u.id,
                 details=body.model_dump(exclude_none=True))
    return _row(u)


@router.get("/governance/controls", tags=["governance"])
def controls(p: Principal = Depends(require("governance:read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(GovernanceControl).where(GovernanceControl.org_id == p.org_id).order_by(GovernanceControl.framework, GovernanceControl.reference))
    return {"notice_ar": "مجالات مرجعية قابلة للتهيئة لدعم المراجعة وليست دليلاً على الامتثال النظامي.",
            "notice_en": "Configurable reference areas to aid review — not evidence of legal compliance.",
            "items": [_row(c) for c in rows]}


@router.get("/governance/evaluations", tags=["governance"])
def evaluations(p: Principal = Depends(require("governance:read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(ModelEvaluation).where(ModelEvaluation.org_id == p.org_id).order_by(ModelEvaluation.created_at.desc()).limit(20))
    return [_row(e) for e in rows]


@router.post("/governance/evaluations/run", status_code=201, tags=["governance"])
def run_eval(p: Principal = Depends(require("governance:manage")), db: Session = Depends(get_db)):
    ev = run_evaluation(db, p)
    audit.record(db, category="GOVERNANCE", action="evaluation_run", principal=p, resource_type="model_evaluation", resource_id=ev.id,
                 details={"metrics": {k: v for k, v in ev.metrics.items() if not isinstance(v, dict)}})
    return _row(ev)


# ================================================================ audit
@router.get("/audit", tags=["audit"])
def audit_list(p: Principal = Depends(require("audit:read")), db: Session = Depends(get_db), category: str = "", action: str = "",
               outcome: str = "", actor_id: uuid.UUID | None = None, resource_id: str = "", q: str = "",
               date_from: datetime | None = None, date_to: datetime | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
    conds = [AuditLog.org_id == p.org_id]
    for col, val in ((AuditLog.category, category), (AuditLog.outcome, outcome), (AuditLog.resource_id, resource_id)):
        if val:
            conds.append(col == val)
    if action:
        conds.append(AuditLog.action.ilike(f"%{action}%"))
    if q:
        conds.append(AuditLog.action.ilike(f"%{q}%") | AuditLog.resource_type.ilike(f"%{q}%") | AuditLog.resource_id.ilike(f"%{q}%"))
    if actor_id:
        conds.append(AuditLog.actor_id == actor_id)
    if date_from:
        conds.append(AuditLog.created_at >= date_from)
    if date_to:
        conds.append(AuditLog.created_at <= date_to)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*conds))
    rows = db.scalars(select(AuditLog).where(*conds).order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": str(a.id), "created_at": a.created_at, "category": a.category, "action": a.action, "outcome": a.outcome,
                       "actor_type": a.actor_type, "actor_name_ar": a.actor.full_name_ar if a.actor else None,
                       "actor_name_en": a.actor.full_name_en if a.actor else None, "resource_type": a.resource_type,
                       "resource_id": a.resource_id, "ip_address": str(a.ip_address) if a.ip_address else None, "details": a.details,
                       "request_id": a.request_id} for a in rows],
            "total": total or 0, "page": page, "page_size": page_size}


# ================================================================ dashboard
@router.get("/dashboard/summary", tags=["dashboard"])
def dashboard(p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db), days: int = Query(90, ge=7, le=365),
              category: str = ""):
    org = p.org_id
    since = datetime.now(timezone.utc) - timedelta(days=days)
    base = [FintechApplication.org_id == org, FintechApplication.deleted_at.is_(None)]
    if category:
        base.append(FintechApplication.service_category == category)
    by_status = dict(db.execute(select(FintechApplication.status, func.count()).where(*base).group_by(FintechApplication.status)).all())
    by_status = {k.value: v for k, v in by_status.items()}
    by_cat = {k.value: v for k, v in db.execute(select(FintechApplication.service_category, func.count()).where(*base)
                                                 .group_by(FintechApplication.service_category)).all()}
    total = sum(by_status.values())
    under_review = sum(by_status.get(s, 0) for s in ("SUBMITTED", "DOCUMENT_PROCESSING", "AI_ANALYSIS", "PENDING_HUMAN_REVIEW"))
    completed = db.scalar(select(func.count()).select_from(AssessmentDraft).where(
        AssessmentDraft.org_id == org, AssessmentDraft.status.in_(["APPROVED_FOR_NEXT_STAGE", "REJECTED", "RETURNED"]))) or 0
    week = func.date_trunc("week", FintechApplication.created_at)
    trend = [{"week": w.date().isoformat(), "count": c} for w, c in db.execute(
        select(week, func.count()).where(*base, FintechApplication.created_at >= since).group_by(week).order_by(week)).all()]
    # risk indicators from latest drafts
    latest = select(AssessmentDraft.application_id, func.max(AssessmentDraft.version).label("v")).where(
        AssessmentDraft.org_id == org).group_by(AssessmentDraft.application_id).subquery()
    latest_drafts = db.scalars(select(AssessmentDraft).join(latest, and_(AssessmentDraft.application_id == latest.c.application_id,
                                                                         AssessmentDraft.version == latest.c.v))).all()
    risk_dist: dict[str, int] = {}
    for d in latest_drafts:
        risk_dist[d.overall_risk] = risk_dist.get(d.overall_risk, 0) + 1
    risk_ind = db.scalar(select(func.count()).select_from(AssessmentFinding).where(
        AssessmentFinding.org_id == org, AssessmentFinding.category == "RISK",
        AssessmentFinding.draft_id.in_([d.id for d in latest_drafts]))) or 0
    durations = [r.duration_ms for r in db.scalars(select(AgentRun).where(AgentRun.org_id == org, AgentRun.status != "FAILED",
                                                                          AgentRun.duration_ms > 0))]
    # time from submission to first review decision (hours)
    rev_times = []
    for a_id, sub, first in db.execute(select(FintechApplication.id, FintechApplication.submitted_at, func.min(AnalystReview.created_at))
                                       .join(AnalystReview, AnalystReview.application_id == FintechApplication.id)
                                       .where(*base).group_by(FintechApplication.id, FintechApplication.submitted_at)).all():
        if sub and first:
            rev_times.append((first - sub).total_seconds() / 3600)
    workload = []
    for u in db.scalars(select(User).where(User.org_id == org, User.deleted_at.is_(None))):
        if not any(r in ("analyst", "supervisor") for r in u.role_codes):
            continue
        rows = dict(db.execute(select(FintechApplication.status, func.count()).where(*base, FintechApplication.assigned_analyst_id == u.id)
                               .group_by(FintechApplication.status)).all())
        workload.append({"user_id": str(u.id), "name_ar": u.full_name_ar, "name_en": u.full_name_en,
                         "open": sum(v for k, v in rows.items() if k not in (S.CLOSED, S.APPROVED_FOR_NEXT_REVIEW_STAGE)),
                         "pending_review": rows.get(S.PENDING_HUMAN_REVIEW, 0)})
    inv = db.execute(select(func.count(), func.avg(ModelInvocation.latency_ms), func.sum(ModelInvocation.tokens_in + ModelInvocation.tokens_out),
                            func.sum(ModelInvocation.cost_usd), func.count().filter(ModelInvocation.success.is_(False)))
                     .where(ModelInvocation.org_id == org, ModelInvocation.created_at >= since)).first()
    cits = db.execute(select(func.count(), func.count().filter(AssessmentCitation.verified.is_(True)))
                      .where(AssessmentCitation.org_id == org)).first()
    recent = db.execute(select(AssessmentFinding, FintechApplication).join(AssessmentDraft, AssessmentDraft.id == AssessmentFinding.draft_id)
                        .join(FintechApplication, FintechApplication.id == AssessmentDraft.application_id)
                        .where(AssessmentFinding.org_id == org, AssessmentFinding.severity.in_(["HIGH", "CRITICAL"]),
                               AssessmentDraft.id.in_([d.id for d in latest_drafts]))
                        .order_by(AssessmentFinding.created_at.desc()).limit(6)).all()
    activity = db.scalars(select(AuditLog).where(AuditLog.org_id == org, AuditLog.category.in_(["APPLICATION", "REVIEW", "AGENT", "DOCUMENT"]))
                          .order_by(AuditLog.created_at.desc()).limit(10)).all()
    return {
        "synthetic": True,
        "kpis": {"total_applications": total, "under_review": under_review, "completed_assessments": completed,
                 "requires_information": by_status.get("ADDITIONAL_INFORMATION_REQUIRED", 0), "risk_indicators": risk_ind,
                 "regulatory_documents": db.scalar(select(func.count()).select_from(RegulatoryDocument).where(
                     RegulatoryDocument.org_id == org, RegulatoryDocument.deleted_at.is_(None))) or 0,
                 "avg_assessment_seconds": round(statistics.mean(durations) / 1000, 2) if durations else None,
                 "avg_hours_to_first_review": round(statistics.mean(rev_times), 1) if rev_times else None,
                 "ai_success_rate": round(1 - (inv[4] or 0) / inv[0], 4) if inv and inv[0] else None},
        "by_status": by_status, "by_category": by_cat, "trend": trend, "risk_distribution": risk_dist, "workload": workload,
        "ai": {"invocations": inv[0] if inv else 0, "avg_latency_ms": round(float(inv[1]), 1) if inv and inv[1] else None,
               "tokens": int(inv[2] or 0) if inv else 0, "cost_usd": round(float(inv[3] or 0), 4) if inv else 0,
               "runs": len(durations), "citation_verification_rate": round((cits[1] or 0) / cits[0], 4) if cits and cits[0] else None,
               "is_mock": get_ai().is_mock},
        "recent_findings": [{"id": str(f.id), "severity": f.severity, "category": f.category, "title_ar": f.title_ar, "title_en": f.title_en,
                             "application_id": str(a.id), "reference": a.reference, "company_name_ar": a.company_name_ar,
                             "company_name_en": a.company_name_en, "created_at": f.created_at} for f, a in recent],
        "activity": [{"id": str(a.id), "action": a.action, "category": a.category, "created_at": a.created_at, "actor_type": a.actor_type,
                      "actor_name_ar": a.actor.full_name_ar if a.actor else None, "actor_name_en": a.actor.full_name_en if a.actor else None,
                      "resource_type": a.resource_type, "resource_id": a.resource_id} for a in activity],
    }


# ================================================================ observability
def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, int(q * (len(v) - 1)))], 1)


@router.get("/observability/metrics", tags=["observability"])
def observability(p: Principal = Depends(require("audit:read")), db: Session = Depends(get_db), hours: int = Query(168, ge=1, le=2160)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    org = p.org_id
    req = db.execute(select(RequestMetric.route, RequestMetric.latency_ms, RequestMetric.status_code).where(RequestMetric.created_at >= since)).all()
    lat = [r[1] for r in req]
    routes: dict[str, list[float]] = {}
    for r in req:
        routes.setdefault(r[0], []).append(r[1])
    hourly_bucket = func.date_trunc("hour", RequestMetric.created_at)
    series = [{"t": t.isoformat(), "requests": n, "errors": e or 0, "p95": round(float(p95 or 0), 1)} for t, n, e, p95 in db.execute(
        select(hourly_bucket, func.count(), func.count().filter(RequestMetric.status_code >= 500),
               func.percentile_cont(0.95).within_group(RequestMetric.latency_ms))
        .where(RequestMetric.created_at >= since).group_by(hourly_bucket).order_by(hourly_bucket)).all()]
    inv = db.scalars(select(ModelInvocation).where(ModelInvocation.org_id == org, ModelInvocation.created_at >= since)).all()
    by_op: dict[str, dict] = {}
    for i in inv:
        d = by_op.setdefault(f"{i.provider}:{i.operation}", {"count": 0, "latency": [], "tokens": 0, "cost": 0.0, "failures": 0, "mock": i.is_mock})
        d["count"] += 1
        d["latency"].append(i.latency_ms)
        d["tokens"] += i.tokens_in + i.tokens_out
        d["cost"] += i.cost_usd
        d["failures"] += 0 if i.success else 1
    runs = db.scalars(select(AgentRun).where(AgentRun.org_id == org, AgentRun.created_at >= since)).all()
    tools = db.scalars(select(AuditLog).where(AuditLog.org_id == org, AuditLog.category == "MCP", AuditLog.created_at >= since,
                                              AuditLog.action.in_(["tool_executed", "tool_failed"]))).all()
    tool_stats: dict[str, dict] = {}
    for t in tools:
        d = tool_stats.setdefault(t.resource_id, {"calls": 0, "failures": 0, "latency": []})
        d["calls"] += 1
        d["failures"] += 1 if t.action == "tool_failed" else 0
        if t.details.get("duration_ms") is not None:
            d["latency"].append(t.details["duration_ms"])
    retr = db.scalars(select(AuditLog).where(AuditLog.org_id == org, AuditLog.category == "RETRIEVAL", AuditLog.created_at >= since)).all()
    rl = [r.details.get("latency_ms") for r in retr if r.details.get("latency_ms") is not None]
    cits = db.execute(select(func.count(), func.count().filter(AssessmentCitation.verified.is_(True)))
                      .where(AssessmentCitation.org_id == org, AssessmentCitation.created_at >= since)).first()
    findings = db.execute(select(AssessmentFinding.analyst_status, func.count()).where(AssessmentFinding.org_id == org)
                          .group_by(AssessmentFinding.analyst_status)).all()
    fs = dict(findings)
    reviewed = sum(v for k, v in fs.items() if k != "UNREVIEWED")
    evals = db.scalars(select(ModelEvaluation).where(ModelEvaluation.org_id == org).order_by(ModelEvaluation.created_at.desc()).limit(10)).all()
    return {
        "window_hours": hours,
        "api": {"requests": len(lat), "p50_ms": _pct(lat, .5), "p95_ms": _pct(lat, .95),
                "errors_5xx": sum(1 for r in req if r[2] >= 500), "errors_4xx": sum(1 for r in req if 400 <= r[2] < 500),
                "series": series,
                "slowest_routes": sorted([{"route": k, "p95_ms": _pct(v, .95), "count": len(v)} for k, v in routes.items()],
                                         key=lambda x: -(x["p95_ms"] or 0))[:8]},
        "models": [{"key": k, "count": v["count"], "avg_latency_ms": round(statistics.mean(v["latency"]), 1), "p95_latency_ms": _pct(v["latency"], .95),
                    "tokens": v["tokens"], "cost_usd": round(v["cost"], 4), "failures": v["failures"], "is_mock": v["mock"]} for k, v in by_op.items()],
        "agents": {"runs": len(runs), "failed": sum(1 for r in runs if r.status == "FAILED"),
                   "avg_duration_ms": round(statistics.mean([r.duration_ms for r in runs if r.duration_ms]), 1) if any(r.duration_ms for r in runs) else None,
                   "avg_tool_calls": round(statistics.mean([r.tool_call_count for r in runs]), 1) if runs else None},
        "tools": [{"tool": k, "calls": v["calls"], "failures": v["failures"], "p95_ms": _pct(v["latency"], .95)} for k, v in sorted(tool_stats.items())],
        "retrieval": {"queries": len(retr), "p50_ms": _pct(rl, .5), "p95_ms": _pct(rl, .95)},
        "citations": {"total": cits[0] if cits else 0, "verified": int(cits[1] or 0) if cits else 0,
                      "accuracy": round((cits[1] or 0) / cits[0], 4) if cits and cits[0] else None},
        "human_corrections": {"reviewed_findings": reviewed, "edited": fs.get("EDITED", 0), "dismissed": fs.get("DISMISSED", 0),
                              "correction_rate": round((fs.get("EDITED", 0) + fs.get("DISMISSED", 0)) / reviewed, 4) if reviewed else None},
        "evaluations": [{"id": str(e.id), "created_at": e.created_at, "model": e.model_name, "metrics": e.metrics, "is_mock": e.is_mock} for e in evals],
    }


# ================================================================ system
@router.get("/system/info", tags=["system"])
def system_info():
    ai = get_ai()
    return {"app": settings.app_name, "environment": settings.environment, "demo_mode": settings.demo_mode,
            "synthetic_data": True, "ai_mock": ai.is_mock, "embedding_mock": ai.embedder.is_mock, "ai_provider": ai.cfg.provider,
            "ai_model": ai.llm.model, "vector_backend": "pgvector" if pgvector_available() else "array",
            "redis": limiter.healthy(), "disclaimer_ar": "منصة عرض مستقلة ببيانات اصطناعية؛ ليست نظاماً رسمياً للبنك المركزي السعودي ولا تحظى بتأييده.",
            "disclaimer_en": "Independent demonstration platform with synthetic data; not an official SAMA system and not endorsed by SAMA."}


@router.get("/system/settings", tags=["system"])
def get_settings_api(p: Principal = Depends(require("settings:manage")), db: Session = Depends(get_db)):
    rows = db.scalars(select(SystemSetting).where((SystemSetting.org_id == p.org_id) | SystemSetting.org_id.is_(None))).all()
    return {"settings": [{"key": r.key, "value": r.value, "description": r.description, "scope": "org" if r.org_id else "global"} for r in rows],
            "runtime": {"rate_limit_per_minute": settings.rate_limit_per_minute, "max_upload_mb": settings.max_upload_mb,
                        "file_scanner": settings.file_scanner, "data_retention_days": settings.data_retention_days,
                        "agent_max_steps": settings.agent_max_steps, "agent_max_tool_calls": settings.agent_max_tool_calls,
                        "agent_token_budget": settings.agent_token_budget, "agent_timeout_seconds": settings.agent_timeout_seconds,
                        "rag_top_k": settings.rag_top_k, "rag_min_score": settings.rag_min_score}}


_ = principal_from_user  # re-exported for scripts
