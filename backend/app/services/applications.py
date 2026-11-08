"""Fintech application domain logic: tenant-scoped access, status workflow, documents, comments."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, Forbidden, NotFound
from app.core.security import Principal
from app.models import (
    ApplicationComment,
    ApplicationDocument,
    ApplicationEvent,
    ApplicationStatus as S,
    DocumentType,
    FintechApplication,
    User,
)
from app.rag.extract import extract, validate_file
from app.services import audit
from app.services.storage import get_storage, new_key, scan_bytes

# Deterministic workflow: allowed transitions and who may perform them.
TRANSITIONS: dict[S, dict[S, str]] = {
    S.DRAFT: {S.SUBMITTED: "applications:write", S.CLOSED: "applications:write"},
    S.SUBMITTED: {S.DOCUMENT_PROCESSING: "applications:write", S.AI_ANALYSIS: "assessments:run",
                  S.ADDITIONAL_INFORMATION_REQUIRED: "reviews:write", S.CLOSED: "applications:write"},
    S.DOCUMENT_PROCESSING: {S.AI_ANALYSIS: "assessments:run", S.SUBMITTED: "applications:write"},
    S.AI_ANALYSIS: {S.PENDING_HUMAN_REVIEW: "assessments:run", S.SUBMITTED: "assessments:run"},
    S.PENDING_HUMAN_REVIEW: {S.ADDITIONAL_INFORMATION_REQUIRED: "reviews:write",
                             S.APPROVED_FOR_NEXT_REVIEW_STAGE: "reviews:approve", S.SUBMITTED: "reviews:write",
                             S.AI_ANALYSIS: "assessments:run", S.CLOSED: "reviews:approve"},
    S.ADDITIONAL_INFORMATION_REQUIRED: {S.SUBMITTED: "applications:write", S.CLOSED: "applications:write"},
    S.APPROVED_FOR_NEXT_REVIEW_STAGE: {S.CLOSED: "reviews:approve"},
    S.CLOSED: {},
}


def get_app(db: Session, principal: Principal, app_id: uuid.UUID) -> FintechApplication:
    app = db.get(FintechApplication, app_id)
    # tenant isolation: another org's application is reported as not found (no existence oracle)
    if app is None or app.deleted_at is not None or app.org_id != principal.org_id:
        raise NotFound("Application", "الطلب")
    return app


def new_reference(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    for _ in range(10):
        ref = f"FT-{year}-{secrets.randbelow(90000) + 10000}"
        if not db.scalar(select(FintechApplication.id).where(FintechApplication.reference == ref)):
            return ref
    raise AppError("Could not allocate reference")


def event(db: Session, app: FintechApplication, principal: Principal | None, event_type: str, *, from_status=None,
          to_status=None, details: dict | None = None) -> None:
    db.add(ApplicationEvent(org_id=app.org_id, application_id=app.id, actor_id=principal.user_id if principal else None,
                            event_type=event_type, from_status=from_status, to_status=to_status, details=details or {}))


def transition(db: Session, principal: Principal, app: FintechApplication, to: S, *, reason: str = "",
               system: bool = False) -> FintechApplication:
    allowed = TRANSITIONS.get(app.status, {})
    if to not in allowed:
        raise AppError(f"Transition {app.status.value} → {to.value} is not allowed",
                       "لا يمكن نقل الطلب إلى هذه الحالة من حالته الحالية", status_code=409, code="INVALID_TRANSITION")
    perm = allowed[to]
    if not system and not principal.has(perm):
        raise Forbidden(details={"missing_permissions": [perm]})
    frm = app.status
    app.status = to
    if to == S.SUBMITTED and app.submitted_at is None:
        app.submitted_at = datetime.now(timezone.utc)
    event(db, app, principal, "STATUS_CHANGED", from_status=frm.value, to_status=to.value, details={"reason": reason})
    audit.record(db, category="APPLICATION", action="status_changed", principal=principal, resource_type="application",
                 resource_id=app.id, details={"from": frm.value, "to": to.value, "reason": reason})
    return app


def assign(db: Session, principal: Principal, app: FintechApplication, analyst_id: uuid.UUID | None) -> FintechApplication:
    if analyst_id is not None:
        analyst = db.get(User, analyst_id)
        if analyst is None or analyst.org_id != principal.org_id or not analyst.is_active:
            raise NotFound("Analyst", "المحلل")
    app.assigned_analyst_id = analyst_id
    event(db, app, principal, "ASSIGNED", details={"analyst_id": str(analyst_id) if analyst_id else None})
    audit.record(db, category="APPLICATION", action="analyst_assigned", principal=principal, resource_type="application",
                 resource_id=app.id, details={"analyst_id": str(analyst_id) if analyst_id else None})
    return app


def upload_document(db: Session, principal: Principal, app: FintechApplication, *, filename: str, data: bytes,
                    document_type: DocumentType) -> ApplicationDocument:
    content_type = validate_file(filename, data, settings.max_upload_mb)
    scan = scan_bytes(data)
    if scan.status == "INFECTED":
        audit.record(db, category="DOCUMENT", action="upload_blocked_malware", principal=principal, outcome="DENIED",
                     resource_type="application", resource_id=app.id, details={"filename": filename})
        raise AppError("File failed malware scanning", "لم يجتز الملف فحص البرمجيات الضارة", status_code=422, code="INFECTED_FILE")
    key = get_storage().put(new_key(principal.org_id, "applications", filename), data)
    doc = ApplicationDocument(org_id=app.org_id, application_id=app.id, document_type=document_type, filename=filename[:255],
                              content_type=content_type, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                              storage_key=key, uploaded_by_id=principal.user_id, scan_status=scan.status)
    try:
        ex = extract(filename, data)
        doc.extracted_text = ex.full_text[:200_000]
        doc.page_count = len(ex.pages)
        doc.processing_status = "PROCESSED"
    except AppError as e:
        doc.processing_status = "FAILED"
        doc.processing_error = e.message
    db.add(doc)
    db.flush()
    event(db, app, principal, "DOCUMENT_UPLOADED", details={"document_id": str(doc.id), "type": document_type.value,
                                                            "filename": filename})
    audit.record(db, category="DOCUMENT", action="application_document_uploaded", principal=principal,
                 resource_type="application_document", resource_id=doc.id,
                 details={"application_id": str(app.id), "type": document_type.value, "size": len(data), "scan": scan.status})
    return doc


def add_comment(db: Session, principal: Principal, app: FintechApplication, body: str, kind: str = "COMMENT") -> ApplicationComment:
    c = ApplicationComment(org_id=app.org_id, application_id=app.id, author_id=principal.user_id, body=body, kind=kind)
    db.add(c)
    db.flush()
    event(db, app, principal, "INFO_REQUESTED" if kind == "INFO_REQUEST" else "COMMENT_ADDED", details={"comment_id": str(c.id)})
    audit.record(db, category="APPLICATION", action="comment_added" if kind == "COMMENT" else "information_requested",
                 principal=principal, resource_type="application", resource_id=app.id, details={"kind": kind})
    return c


def count_by_status(db: Session, org_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(select(FintechApplication.status, func.count()).where(
        FintechApplication.org_id == org_id, FintechApplication.deleted_at.is_(None)).group_by(FintechApplication.status))
    return {s.value: int(c) for s, c in rows}
