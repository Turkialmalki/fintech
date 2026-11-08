from __future__ import annotations

import threading
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.graph import GRAPH_DESCRIPTION, create_run, execute_run
from app.api.deps import require
from app.core.db import get_db
from app.core.errors import NotFound
from app.core.security import Principal
from app.models import AgentRun, AnalystReview, AssessmentDraft, FintechApplication, User
from app.reports.pdf import build_report
from app.schemas.common import DecisionIn, DraftEditIn, RunIn
from app.services import applications as apps
from app.services import assessments as svc
from app.services import audit
from app.api.v1.applications import to_out

router = APIRouter(tags=["assessments"])


def citation_out(c) -> dict:
    return {"id": str(c.id), "source_type": c.source_type, "chunk_id": str(c.chunk_id) if c.chunk_id else None,
            "application_document_id": str(c.application_document_id) if c.application_document_id else None,
            "document_code": c.document_code, "document_title": c.document_title, "version_label": c.version_label,
            "page_number": c.page_number, "section": c.section, "quote": c.quote, "score": c.score, "verified": c.verified}


def draft_out(d: AssessmentDraft) -> dict:
    return {"id": str(d.id), "application_id": str(d.application_id), "agent_run_id": str(d.agent_run_id) if d.agent_run_id else None,
            "version": d.version, "parent_id": str(d.parent_id) if d.parent_id else None, "status": d.status, "authored_by": d.authored_by,
            "edited_by_name_ar": d.edited_by.full_name_ar if d.edited_by else None, "edited_by_name_en": d.edited_by.full_name_en if d.edited_by else None,
            "summary_ar": d.summary_ar, "summary_en": d.summary_en, "analyst_notes": d.analyst_notes, "limitations_ar": d.limitations_ar,
            "limitations_en": d.limitations_en, "overall_risk": d.overall_risk, "extracted_profile": d.extracted_profile,
            "missing_documents": d.missing_documents, "generation_meta": d.generation_meta, "created_at": d.created_at.isoformat(),
            "findings": [{"id": str(f.id), "sequence": f.sequence, "category": f.category, "severity": f.severity, "title_ar": f.title_ar,
                          "title_en": f.title_en, "evidence_ar": f.evidence_ar, "evidence_en": f.evidence_en,
                          "interpretation_ar": f.interpretation_ar, "interpretation_en": f.interpretation_en, "uncertainty": f.uncertainty,
                          "source_agent": f.source_agent, "origin": f.origin, "requirement_code": f.requirement_code,
                          "analyst_status": f.analyst_status, "citations": [citation_out(c) for c in f.citations]} for f in d.findings]}


def run_out(r: AgentRun, steps: bool = False) -> dict:
    out = {"id": str(r.id), "application_id": str(r.application_id) if r.application_id else None, "workflow": r.workflow,
           "status": r.status, "ai_provider": r.ai_provider, "ai_model": r.ai_model, "tool_transport": r.tool_transport,
           "started_at": r.started_at, "finished_at": r.finished_at, "duration_ms": r.duration_ms, "step_count": r.step_count,
           "tool_call_count": r.tool_call_count, "tokens_in": r.tokens_in, "tokens_out": r.tokens_out, "cost_usd": r.cost_usd,
           "error": r.error, "budget": r.budget, "final_state": r.final_state, "created_at": r.created_at,
           "triggered_by_name_ar": r.triggered_by.full_name_ar if r.triggered_by else None,
           "triggered_by_name_en": r.triggered_by.full_name_en if r.triggered_by else None}
    if steps:
        out["steps"] = [{"id": str(s.id), "sequence": s.sequence, "agent": s.agent, "step_type": s.step_type, "name": s.name,
                         "status": s.status, "attempt": s.attempt, "duration_ms": s.duration_ms, "input": s.input, "output": s.output,
                         "error": s.error, "tokens_in": s.tokens_in, "tokens_out": s.tokens_out, "created_at": s.created_at} for s in r.steps]
    return out


def review_out(r: AnalystReview) -> dict:
    return {"id": str(r.id), "decision": r.decision, "comment": r.comment, "confirmed": r.confirmed, "created_at": r.created_at.isoformat(),
            "reviewer_name_ar": r.reviewer.full_name_ar, "reviewer_name_en": r.reviewer.full_name_en, "draft_id": str(r.draft_id)}


@router.post("/assessments/run", status_code=202)
def run_assessment(body: RunIn, p: Principal = Depends(require("assessments:run"))):
    run_id = create_run(p, body.application_id)
    # Background execution (in production this is a worker; the in-process thread keeps the demo self-contained).
    threading.Thread(target=execute_run, args=(run_id, p), daemon=True, name=f"agent-run-{run_id}").start()
    return {"run_id": str(run_id), "status": "QUEUED"}


@router.get("/assessments/runs")
def list_runs(p: Principal = Depends(require("assessments:read")), db: Session = Depends(get_db),
              application_id: uuid.UUID | None = None, limit: int = Query(30, le=100)):
    conds = [AgentRun.org_id == p.org_id]
    if application_id:
        conds.append(AgentRun.application_id == application_id)
    rows = db.scalars(select(AgentRun).where(*conds).order_by(AgentRun.created_at.desc()).limit(limit)).all()
    apps_by_id = {a.id: a for a in db.scalars(select(FintechApplication).where(
        FintechApplication.id.in_([r.application_id for r in rows if r.application_id]))).all()}
    return [{**run_out(r), "application_reference": apps_by_id[r.application_id].reference if r.application_id in apps_by_id else None,
             "company_name_ar": apps_by_id[r.application_id].company_name_ar if r.application_id in apps_by_id else None,
             "company_name_en": apps_by_id[r.application_id].company_name_en if r.application_id in apps_by_id else None} for r in rows]


@router.get("/assessments/runs/{run_id}")
def get_run(run_id: uuid.UUID, p: Principal = Depends(require("assessments:read")), db: Session = Depends(get_db)):
    r = db.get(AgentRun, run_id)
    if not r or r.org_id != p.org_id:
        raise NotFound("Run", "عملية التشغيل")
    return run_out(r, steps=True)


@router.get("/agents/graph")
def agent_graph(p: Principal = Depends(require("assessments:read"))):
    return GRAPH_DESCRIPTION


@router.get("/applications/{app_id}/assessments")
def app_assessments(app_id: uuid.UUID, p: Principal = Depends(require("assessments:read")), db: Session = Depends(get_db)):
    a = apps.get_app(db, p, app_id)
    rows = db.scalars(select(AssessmentDraft).where(AssessmentDraft.application_id == a.id, AssessmentDraft.deleted_at.is_(None))
                      .order_by(AssessmentDraft.version.desc())).all()
    return [{k: v for k, v in draft_out(d).items() if k != "findings"} | {"finding_count": len(d.findings)} for d in rows]


@router.get("/assessments/{draft_id}")
def get_draft(draft_id: uuid.UUID, p: Principal = Depends(require("assessments:read")), db: Session = Depends(get_db)):
    d = svc.get_draft(db, p, draft_id)
    app = apps.get_app(db, p, d.application_id)
    reviews = db.scalars(select(AnalystReview).where(AnalystReview.application_id == app.id).order_by(AnalystReview.created_at.desc())).all()
    versions = db.scalars(select(AssessmentDraft).where(AssessmentDraft.application_id == app.id).order_by(AssessmentDraft.version.desc())).all()
    return {**draft_out(d), "application": to_out(db, app, p).model_dump(mode="json"), "reviews": [review_out(r) for r in reviews],
            "versions": [{"id": str(v.id), "version": v.version, "status": v.status, "authored_by": v.authored_by,
                          "created_at": v.created_at.isoformat()} for v in versions]}


@router.patch("/assessments/{draft_id}")
def edit(draft_id: uuid.UUID, body: DraftEditIn, p: Principal = Depends(require("reviews:write")), db: Session = Depends(get_db)):
    d = svc.get_draft(db, p, draft_id)
    new = svc.edit_draft(db, p, d, summary_ar=body.summary_ar, summary_en=body.summary_en, analyst_notes=body.analyst_notes,
                         finding_updates=body.finding_updates,
                         new_findings=[svc.FindingIn.model_validate({**f, "origin": "HUMAN"}) for f in body.new_findings])
    return draft_out(new)


@router.post("/assessments/{draft_id}/decision")
def decision(draft_id: uuid.UUID, body: DecisionIn, p: Principal = Depends(require("reviews:write")), db: Session = Depends(get_db)):
    d = svc.get_draft(db, p, draft_id)
    r = svc.decide(db, p, d, body.decision, body.comment, body.confirmed)
    return {"review": review_out(r), "draft_status": d.status}


@router.get("/reviews/queue")
def review_queue(p: Principal = Depends(require("assessments:read")), db: Session = Depends(get_db), status: str = "PENDING_REVIEW"):
    statuses = [s for s in status.split(",") if s]
    rows = db.scalars(select(AssessmentDraft).where(AssessmentDraft.org_id == p.org_id, AssessmentDraft.deleted_at.is_(None),
                                                    AssessmentDraft.status.in_(statuses)).order_by(AssessmentDraft.created_at.desc())).all()
    out = []
    for d in rows:
        a = db.get(FintechApplication, d.application_id)
        out.append({**{k: v for k, v in draft_out(d).items() if k != "findings"}, "finding_count": len(d.findings),
                    "high_count": sum(1 for f in d.findings if f.severity in ("HIGH", "CRITICAL")),
                    "unverified_citations": sum(1 for f in d.findings for c in f.citations if not c.verified),
                    "application_reference": a.reference, "company_name_ar": a.company_name_ar, "company_name_en": a.company_name_en,
                    "service_category": a.service_category.value, "application_status": a.status.value,
                    "assigned_analyst_id": str(a.assigned_analyst_id) if a.assigned_analyst_id else None})
    return out


@router.get("/assessments/{draft_id}/report.pdf")
def report(draft_id: uuid.UUID, lang: str = Query("ar", pattern="^(ar|en)$"), p: Principal = Depends(require("assessments:read")),
           db: Session = Depends(get_db)):
    d = svc.get_draft(db, p, draft_id)
    app = apps.get_app(db, p, d.application_id)
    reviews = db.scalars(select(AnalystReview).where(AnalystReview.draft_id == d.id).order_by(AnalystReview.created_at)).all()
    user = db.get(User, p.user_id)
    pdf = build_report(lang=lang, app=to_out(db, app, p).model_dump(mode="json"), draft=draft_out(d),
                       reviews=[review_out(r) for r in reviews], generated_by=user.full_name_ar if lang == "ar" else user.full_name_en)
    audit.record(db, category="REVIEW", action="report_exported", principal=p, resource_type="assessment_draft", resource_id=d.id,
                 details={"lang": lang, "bytes": len(pdf)})
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="assessment-{app.reference}-v{d.version}-{lang}.pdf"'})


@router.get("/assessments/stats/summary")
def stats(p: Principal = Depends(require("assessments:read")), db: Session = Depends(get_db)):
    by_status = dict(db.execute(select(AgentRun.status, func.count()).where(AgentRun.org_id == p.org_id).group_by(AgentRun.status)).all())
    return {"runs_by_status": by_status}
