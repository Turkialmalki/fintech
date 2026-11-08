from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.db import get_db
from app.core.errors import AppError, NotFound
from app.core.security import Principal
from app.models import (
    ApplicationComment,
    ApplicationDocument,
    ApplicationEvent,
    ApplicationStatus as S,
    AssessmentDraft,
    DocumentType,
    FintechApplication,
    ServiceCategory,
)
from app.schemas.common import (
    ApplicationIn,
    ApplicationOut,
    ApplicationPatch,
    AssignIn,
    CommentIn,
    DocumentOut,
    Page,
    TransitionIn,
)
from app.services import applications as svc
from app.services import audit
from app.services.storage import get_storage

router = APIRouter(tags=["applications"])


def to_out(db: Session, a: FintechApplication, principal: Principal | None = None) -> ApplicationOut:
    risk = db.scalar(select(AssessmentDraft.overall_risk).where(AssessmentDraft.application_id == a.id, AssessmentDraft.deleted_at.is_(None))
                     .order_by(AssessmentDraft.version.desc()).limit(1))
    out = ApplicationOut.model_validate(a, from_attributes=True).model_copy(update={
        "service_category": a.service_category.value, "status": a.status.value,
        "assigned_analyst_name_ar": a.assigned_analyst.full_name_ar if a.assigned_analyst else None,
        "assigned_analyst_name_en": a.assigned_analyst.full_name_en if a.assigned_analyst else None,
        "paid_up_capital_sar": float(a.paid_up_capital_sar) if a.paid_up_capital_sar is not None else None,
        "expected_monthly_volume_sar": float(a.expected_monthly_volume_sar) if a.expected_monthly_volume_sar is not None else None,
        "document_count": len(a.documents), "latest_risk": risk,
        "allowed_transitions": [t.value for t, perm in svc.TRANSITIONS.get(a.status, {}).items() if principal is None or principal.has(perm)],
    })
    return out


@router.get("/applications", response_model=Page[ApplicationOut])
def list_applications(
    p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db),
    status: list[str] = Query(default=[]), category: list[str] = Query(default=[]), q: str = "",
    assigned_to: uuid.UUID | None = None, mine: bool = False, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("-created_at", pattern="^-?(created_at|company_name_en|status|reference)$"),
):
    conds = [FintechApplication.org_id == p.org_id, FintechApplication.deleted_at.is_(None)]
    if status:
        conds.append(FintechApplication.status.in_([S(s) for s in status if s in S.__members__]))
    if category:
        conds.append(FintechApplication.service_category.in_([ServiceCategory(c) for c in category if c in ServiceCategory.__members__]))
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(FintechApplication.company_name_ar.ilike(like), FintechApplication.company_name_en.ilike(like),
                         FintechApplication.reference.ilike(like), FintechApplication.commercial_registration.ilike(like)))
    if mine:
        conds.append(FintechApplication.assigned_analyst_id == p.user_id)
    elif assigned_to:
        conds.append(FintechApplication.assigned_analyst_id == assigned_to)
    col = getattr(FintechApplication, sort.lstrip("-"))
    total = db.scalar(select(func.count()).select_from(FintechApplication).where(*conds))
    rows = db.scalars(select(FintechApplication).where(*conds).order_by(col.desc() if sort.startswith("-") else col.asc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[to_out(db, a, p) for a in rows], total=total or 0, page=page, page_size=page_size)


@router.post("/applications", response_model=ApplicationOut, status_code=201)
def create_application(body: ApplicationIn, p: Principal = Depends(require("applications:write")), db: Session = Depends(get_db)):
    data = body.model_dump()
    data["contact_email"] = data["contact_email"] or ""
    a = FintechApplication(org_id=p.org_id, reference=svc.new_reference(db), created_by_id=p.user_id, is_synthetic=True,
                           **{**data, "service_category": ServiceCategory(body.service_category)})
    db.add(a)
    db.flush()
    svc.event(db, a, p, "CREATED")
    audit.record(db, category="APPLICATION", action="application_created", principal=p, resource_type="application",
                 resource_id=a.id, details={"reference": a.reference, "category": body.service_category})
    db.refresh(a)
    return to_out(db, a, p)


@router.get("/applications/{app_id}", response_model=ApplicationOut)
def get_application(app_id: uuid.UUID, p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db)):
    return to_out(db, svc.get_app(db, p, app_id), p)


@router.patch("/applications/{app_id}", response_model=ApplicationOut)
def update_application(app_id: uuid.UUID, body: ApplicationPatch, p: Principal = Depends(require("applications:write")),
                       db: Session = Depends(get_db)):
    a = svc.get_app(db, p, app_id)
    if a.status in (S.CLOSED, S.APPROVED_FOR_NEXT_REVIEW_STAGE, S.AI_ANALYSIS):
        raise AppError("Application cannot be edited in its current status", "لا يمكن تعديل الطلب في حالته الحالية", status_code=409)
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        if k == "service_category" and v:
            v = ServiceCategory(v)
        if k == "contact_email":
            v = v or ""
        setattr(a, k, v)
    svc.event(db, a, p, "UPDATED", details={"fields": sorted(changes)})
    audit.record(db, category="APPLICATION", action="application_updated", principal=p, resource_type="application",
                 resource_id=a.id, details={"fields": sorted(changes)})
    db.flush()
    return to_out(db, a, p)


@router.post("/applications/{app_id}/transition", response_model=ApplicationOut)
def transition(app_id: uuid.UUID, body: TransitionIn, p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db)):
    if body.to_status not in S.__members__:
        raise AppError("Unknown status", "حالة غير معروفة", status_code=422)
    a = svc.get_app(db, p, app_id)
    if S(body.to_status) in (S.AI_ANALYSIS, S.PENDING_HUMAN_REVIEW, S.APPROVED_FOR_NEXT_REVIEW_STAGE):
        raise AppError("This status is set by the assessment and review workflow", "تُحدَّد هذه الحالة عبر مسار التقييم والمراجعة",
                       status_code=409, code="WORKFLOW_MANAGED")
    svc.transition(db, p, a, S(body.to_status), reason=body.reason)
    return to_out(db, a, p)


@router.post("/applications/{app_id}/assign", response_model=ApplicationOut)
def assign(app_id: uuid.UUID, body: AssignIn, p: Principal = Depends(require("applications:assign")), db: Session = Depends(get_db)):
    a = svc.get_app(db, p, app_id)
    svc.assign(db, p, a, body.analyst_id)
    db.flush()
    db.refresh(a)
    return to_out(db, a, p)


@router.get("/applications/{app_id}/events")
def events(app_id: uuid.UUID, p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db)):
    a = svc.get_app(db, p, app_id)
    rows = db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == a.id).order_by(ApplicationEvent.created_at.desc())).all()
    return [{"id": str(e.id), "event_type": e.event_type, "from_status": e.from_status, "to_status": e.to_status, "details": e.details,
             "created_at": e.created_at, "actor_name_ar": e.actor.full_name_ar if e.actor else None,
             "actor_name_en": e.actor.full_name_en if e.actor else None} for e in rows]


@router.get("/applications/{app_id}/comments")
def comments(app_id: uuid.UUID, p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db)):
    a = svc.get_app(db, p, app_id)
    rows = db.scalars(select(ApplicationComment).where(ApplicationComment.application_id == a.id, ApplicationComment.deleted_at.is_(None))
                      .order_by(ApplicationComment.created_at.desc())).all()
    return [{"id": str(c.id), "body": c.body, "kind": c.kind, "created_at": c.created_at, "author_id": str(c.author_id),
             "author_name_ar": c.author.full_name_ar, "author_name_en": c.author.full_name_en} for c in rows]


@router.post("/applications/{app_id}/comments", status_code=201)
def add_comment(app_id: uuid.UUID, body: CommentIn, p: Principal = Depends(require("applications:write")), db: Session = Depends(get_db)):
    c = svc.add_comment(db, p, svc.get_app(db, p, app_id), body.body)
    return {"id": str(c.id)}


@router.post("/applications/{app_id}/request-information", response_model=ApplicationOut)
def request_info(app_id: uuid.UUID, body: CommentIn, p: Principal = Depends(require("reviews:write")), db: Session = Depends(get_db)):
    a = svc.get_app(db, p, app_id)
    if a.status == S.AI_ANALYSIS:
        raise AppError("Wait for the running assessment to finish", "يرجى انتظار اكتمال التقييم الجاري", status_code=409)
    if a.status != S.ADDITIONAL_INFORMATION_REQUIRED:
        svc.transition(db, p, a, S.ADDITIONAL_INFORMATION_REQUIRED, reason=body.body[:300])
    svc.add_comment(db, p, a, body.body, kind="INFO_REQUEST")
    return to_out(db, a, p)


@router.get("/applications/{app_id}/documents", response_model=list[DocumentOut])
def list_documents(app_id: uuid.UUID, p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db)):
    a = svc.get_app(db, p, app_id)
    return [DocumentOut.model_validate(d).model_copy(update={"document_type": d.document_type.value}) for d in a.documents]


@router.post("/applications/{app_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(app_id: uuid.UUID, file: UploadFile = File(...), document_type: str = Form(...),
                          p: Principal = Depends(require("documents:upload")), db: Session = Depends(get_db)):
    if document_type not in DocumentType.__members__:
        raise AppError("Unknown document type", "نوع الوثيقة غير معروف", status_code=422)
    a = svc.get_app(db, p, app_id)
    if a.status in (S.CLOSED, S.APPROVED_FOR_NEXT_REVIEW_STAGE):
        raise AppError("Documents cannot be added in the current status", "لا يمكن إضافة وثائق في الحالة الحالية", status_code=409)
    data = await file.read()
    d = svc.upload_document(db, p, a, filename=file.filename or "upload", data=data, document_type=DocumentType(document_type))
    return DocumentOut.model_validate(d).model_copy(update={"document_type": d.document_type.value})


def _doc(db: Session, p: Principal, doc_id: uuid.UUID) -> ApplicationDocument:
    d = db.get(ApplicationDocument, doc_id)
    if not d or d.org_id != p.org_id or d.deleted_at is not None:
        raise NotFound("Document", "الوثيقة")
    return d


@router.get("/documents/{doc_id}")
def document_detail(doc_id: uuid.UUID, p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db)):
    d = _doc(db, p, doc_id)
    return {**DocumentOut.model_validate(d).model_copy(update={"document_type": d.document_type.value}).model_dump(mode="json"),
            "extracted_text": d.extracted_text, "untrusted_content_notice": "Applicant-supplied content. Treated as data, not instructions."}


@router.get("/documents/{doc_id}/download")
def download(doc_id: uuid.UUID, p: Principal = Depends(require("applications:read")), db: Session = Depends(get_db)):
    d = _doc(db, p, doc_id)
    audit.record(db, category="DOCUMENT", action="application_document_downloaded", principal=p, resource_type="application_document",
                 resource_id=d.id)
    return Response(get_storage().get(d.storage_key), media_type=d.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{d.filename}"', "X-Content-Type-Options": "nosniff"})


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: uuid.UUID, p: Principal = Depends(require("documents:upload")), db: Session = Depends(get_db)):
    from datetime import datetime, timezone

    d = _doc(db, p, doc_id)
    d.deleted_at = datetime.now(timezone.utc)  # soft delete keeps the audit trail intact
    audit.record(db, category="DOCUMENT", action="application_document_deleted", principal=p, resource_type="application_document",
                 resource_id=d.id)
