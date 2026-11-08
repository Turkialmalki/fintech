"""Assessment drafts, findings, citations and the human review workflow."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFound
from app.core.security import Principal
from app.models import (
    AnalystReview,
    ApplicationStatus as S,
    AssessmentCitation,
    AssessmentDraft,
    AssessmentFinding,
    FintechApplication,
    RegulatoryChunk,
)
from app.rag.answer import quote_supported
from app.services import applications as apps
from app.services import audit


class CitationIn(BaseModel):
    source_type: str = "REGULATORY"
    chunk_id: uuid.UUID | None = None
    application_document_id: uuid.UUID | None = None
    quote: str = ""
    score: float = 0.0


class FindingIn(BaseModel):
    category: str = Field(pattern="^(REGULATORY|RISK|GAP|MISSING_INFORMATION|OBSERVATION)$")
    severity: str = Field(default="MEDIUM", pattern="^(INFO|LOW|MEDIUM|HIGH|CRITICAL)$")
    title_ar: str
    title_en: str
    evidence_ar: str = ""
    evidence_en: str = ""
    interpretation_ar: str = ""
    interpretation_en: str = ""
    uncertainty: str = ""
    source_agent: str = ""
    origin: str = Field(default="AI", pattern="^(RULE|AI|HUMAN)$")
    requirement_code: str = ""
    citations: list[CitationIn] = Field(default_factory=list)


class DraftIn(BaseModel):
    summary_ar: str = ""
    summary_en: str = ""
    limitations_ar: str = ""
    limitations_en: str = ""
    overall_risk: str = "UNDETERMINED"
    extracted_profile: dict = Field(default_factory=dict)
    missing_documents: list = Field(default_factory=list)
    generation_meta: dict = Field(default_factory=dict)
    findings: list[FindingIn] = Field(default_factory=list)


def get_draft(db: Session, principal: Principal, draft_id: uuid.UUID) -> AssessmentDraft:
    d = db.get(AssessmentDraft, draft_id)
    if d is None or d.deleted_at is not None or d.org_id != principal.org_id:
        raise NotFound("Assessment draft", "مسودة التقييم")
    return d


def _add_findings(db: Session, principal: Principal, draft: AssessmentDraft, findings: list[FindingIn]) -> None:
    for i, f in enumerate(findings):
        fnd = AssessmentFinding(org_id=draft.org_id, draft_id=draft.id, sequence=i, **f.model_dump(exclude={"citations"}))
        db.add(fnd)
        db.flush()
        for c in f.citations:
            cit = AssessmentCitation(org_id=draft.org_id, finding_id=fnd.id, source_type=c.source_type, quote=c.quote[:2000], score=c.score)
            if c.chunk_id:
                ch = db.get(RegulatoryChunk, c.chunk_id)
                # citations may only point to chunks of the same tenant; verify the quote exists in the chunk
                if ch is None or ch.org_id != draft.org_id:
                    continue
                cit.chunk_id = ch.id
                cit.document_code = ch.document.document_code
                cit.document_title = ch.document.title_ar or ch.document.title_en
                cit.version_label = ch.version.version_label
                cit.page_number = ch.page_number
                cit.section = ch.section
                cit.verified = quote_supported(c.quote, ch.text) if c.quote else False
            elif c.application_document_id:
                cit.application_document_id = c.application_document_id
                cit.verified = bool(c.quote)
            db.add(cit)


def create_draft(db: Session, principal: Principal, app: FintechApplication, data: DraftIn, *,
                 agent_run_id: uuid.UUID | None = None, authored_by: str = "AI") -> AssessmentDraft:
    prev = db.scalar(select(AssessmentDraft).where(AssessmentDraft.application_id == app.id, AssessmentDraft.deleted_at.is_(None))
                     .order_by(AssessmentDraft.version.desc()).limit(1))
    version = (prev.version + 1) if prev else 1
    if prev and prev.status in ("DRAFT", "PENDING_REVIEW", "RETURNED"):
        prev.status = "SUPERSEDED"
    draft = AssessmentDraft(org_id=app.org_id, application_id=app.id, agent_run_id=agent_run_id, version=version,
                            parent_id=prev.id if prev else None, status="DRAFT", authored_by=authored_by,
                            **data.model_dump(exclude={"findings"}))
    db.add(draft)
    db.flush()
    _add_findings(db, principal, draft, data.findings)
    db.flush()
    db.refresh(draft)
    audit.record(db, category="AGENT" if authored_by == "AI" else "REVIEW", action="assessment_draft_created", principal=principal,
                 resource_type="assessment_draft", resource_id=draft.id,
                 details={"application_id": str(app.id), "version": version, "findings": len(data.findings), "run": str(agent_run_id or "")})
    return draft


def submit_for_review(db: Session, principal: Principal, draft: AssessmentDraft) -> AssessmentDraft:
    if draft.status not in ("DRAFT", "RETURNED"):
        raise AppError("Only drafts can be submitted for review", "يمكن إرسال المسودات فقط للمراجعة", status_code=409)
    app = apps.get_app(db, principal, draft.application_id)
    draft.status = "PENDING_REVIEW"
    if app.status == S.AI_ANALYSIS:
        apps.transition(db, principal, app, S.PENDING_HUMAN_REVIEW, reason="assessment draft submitted for human review", system=True)
    audit.record(db, category="REVIEW", action="submitted_for_human_review", principal=principal,
                 resource_type="assessment_draft", resource_id=draft.id)
    return draft


def edit_draft(db: Session, principal: Principal, draft: AssessmentDraft, *, summary_ar: str | None, summary_en: str | None,
               analyst_notes: str | None, finding_updates: list[dict], new_findings: list[FindingIn]) -> AssessmentDraft:
    """Analyst edits create a NEW version (previous versions remain reviewable)."""
    if draft.status not in ("DRAFT", "PENDING_REVIEW", "RETURNED"):
        raise AppError("This draft can no longer be edited", "لم يعد بالإمكان تعديل هذه المسودة", status_code=409)
    app = apps.get_app(db, principal, draft.application_id)
    by_id = {str(u.get("id")): u for u in finding_updates}
    carried: list[FindingIn] = []
    for f in draft.findings:
        upd = by_id.get(str(f.id), {})
        if upd.get("analyst_status") == "DISMISSED_DELETE":
            continue
        data = FindingIn(category=f.category, severity=upd.get("severity", f.severity), title_ar=upd.get("title_ar", f.title_ar),
                         title_en=upd.get("title_en", f.title_en), evidence_ar=f.evidence_ar, evidence_en=f.evidence_en,
                         interpretation_ar=upd.get("interpretation_ar", f.interpretation_ar),
                         interpretation_en=upd.get("interpretation_en", f.interpretation_en), uncertainty=f.uncertainty,
                         source_agent=f.source_agent, origin=f.origin, requirement_code=f.requirement_code,
                         citations=[CitationIn(source_type=c.source_type, chunk_id=c.chunk_id,
                                               application_document_id=c.application_document_id, quote=c.quote, score=c.score)
                                    for c in f.citations])
        carried.append(data)
    status_by_index = []
    for f in draft.findings:
        upd = by_id.get(str(f.id), {})
        if upd.get("analyst_status") == "DISMISSED_DELETE":
            continue
        changed = any(k in upd and upd[k] != getattr(f, k, None) for k in ("severity", "title_ar", "title_en", "interpretation_ar", "interpretation_en"))
        status_by_index.append(upd.get("analyst_status") or ("EDITED" if changed else f.analyst_status))
    for nf in new_findings:
        nf.origin = "HUMAN"
        carried.append(nf)
        status_by_index.append("CONFIRMED")
    new = AssessmentDraft(
        org_id=draft.org_id, application_id=draft.application_id, agent_run_id=draft.agent_run_id,
        version=(db.scalar(select(func.max(AssessmentDraft.version)).where(AssessmentDraft.application_id == app.id)) or 0) + 1,
        parent_id=draft.id, status=draft.status, authored_by="MIXED" if draft.authored_by != "HUMAN" else "HUMAN",
        edited_by_id=principal.user_id, summary_ar=summary_ar if summary_ar is not None else draft.summary_ar,
        summary_en=summary_en if summary_en is not None else draft.summary_en,
        analyst_notes=analyst_notes if analyst_notes is not None else draft.analyst_notes,
        limitations_ar=draft.limitations_ar, limitations_en=draft.limitations_en, overall_risk=draft.overall_risk,
        extracted_profile=draft.extracted_profile, missing_documents=draft.missing_documents,
        generation_meta={**draft.generation_meta, "edited_from_version": draft.version,
                         "summary_edited": summary_ar is not None or summary_en is not None},
    )
    draft.status = "SUPERSEDED"
    db.add(new)
    db.flush()
    _add_findings(db, principal, new, carried)
    db.flush()
    db.refresh(new)
    for f, st in zip(new.findings, status_by_index):
        f.analyst_status = st
    audit.record(db, category="REVIEW", action="assessment_edited", principal=principal, resource_type="assessment_draft",
                 resource_id=new.id, details={"from_version": draft.version, "to_version": new.version,
                                              "finding_updates": len(finding_updates), "new_findings": len(new_findings)})
    return new


DECISIONS = {
    # decision: (required permission, new draft status, application status)
    "APPROVE_FOR_NEXT_STAGE": ("reviews:approve", "APPROVED_FOR_NEXT_STAGE", S.APPROVED_FOR_NEXT_REVIEW_STAGE),
    "RETURN": ("reviews:write", "RETURNED", None),
    "REJECT": ("reviews:approve", "REJECTED", None),
    "REQUEST_INFORMATION": ("reviews:write", "RETURNED", S.ADDITIONAL_INFORMATION_REQUIRED),
    "COMMENT": ("reviews:write", None, None),
}


def decide(db: Session, principal: Principal, draft: AssessmentDraft, decision: str, comment: str, confirmed: bool) -> AnalystReview:
    if decision not in DECISIONS:
        raise AppError("Unknown decision", "قرار غير معروف", status_code=422)
    perm, draft_status, app_status = DECISIONS[decision]
    if not principal.has(perm):
        from app.core.errors import Forbidden

        raise Forbidden(details={"missing_permissions": [perm]})
    consequential = decision in ("APPROVE_FOR_NEXT_STAGE", "REJECT", "REQUEST_INFORMATION")
    if consequential and not confirmed:
        raise AppError("Consequential actions require explicit confirmation", "يتطلب هذا الإجراء تأكيداً صريحاً",
                       status_code=422, code="CONFIRMATION_REQUIRED")
    if principal.actor_type != "USER":
        raise AppError("Review decisions can only be made by a human user", "قرارات المراجعة تُتخذ من مستخدم بشري فقط",
                       status_code=403, code="HUMAN_REQUIRED")
    if draft_status and draft.status not in ("PENDING_REVIEW", "DRAFT", "RETURNED"):
        raise AppError("This draft is not awaiting review", "هذه المسودة ليست بانتظار المراجعة", status_code=409)
    if decision in ("REQUEST_INFORMATION", "RETURN") and not comment.strip():
        raise AppError("A comment is required", "يرجى إضافة ملاحظة توضح السبب", status_code=422)
    app = apps.get_app(db, principal, draft.application_id)
    review = AnalystReview(org_id=draft.org_id, draft_id=draft.id, application_id=app.id, reviewer_id=principal.user_id,
                           decision=decision, comment=comment, confirmed=confirmed)
    db.add(review)
    if draft_status:
        draft.status = draft_status
    if app_status and app.status != app_status:
        if app.status == S.AI_ANALYSIS:
            apps.transition(db, principal, app, S.PENDING_HUMAN_REVIEW, reason="review started", system=True)
        apps.transition(db, principal, app, app_status, reason=f"review decision {decision}")
    if decision == "REQUEST_INFORMATION":
        apps.add_comment(db, principal, app, comment, kind="INFO_REQUEST")
    db.flush()
    audit.record(db, category="REVIEW", action=f"review_{decision.lower()}", principal=principal, resource_type="assessment_draft",
                 resource_id=draft.id, details={"application_id": str(app.id), "confirmed": confirmed, "comment": comment[:300]})
    return review
