from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require
from app.core.db import get_db
from app.core.errors import AppError, NotFound
from app.core.security import Principal
from app.models import RegulatoryChunk, RegulatoryDocument, RegulatoryDocumentVersion, RegulatoryRequirement
from app.rag.answer import answer_question
from app.rag.index import ingest_regulatory_document
from app.rag.retrieve import SearchFilters, hybrid_search
from app.schemas.common import RagIn, RequirementIn, SearchIn
from app.services import audit

router = APIRouter(tags=["regulatory"])


def _version(v: RegulatoryDocumentVersion) -> dict:
    return {"id": str(v.id), "version_number": v.version_number, "version_label": v.version_label, "status": v.status,
            "publication_date": v.publication_date, "effective_date": v.effective_date, "filename": v.filename,
            "content_type": v.content_type, "page_count": v.page_count, "chunk_count": v.chunk_count,
            "indexing_status": v.indexing_status, "indexing_error": v.indexing_error, "sha256": v.sha256,
            "extracted_metadata": v.extracted_metadata, "created_at": v.created_at}


def _doc(d: RegulatoryDocument) -> dict:
    cur = next((v for v in d.versions if v.id == d.current_version_id), d.versions[0] if d.versions else None)
    return {"id": str(d.id), "document_code": d.document_code, "title_ar": d.title_ar, "title_en": d.title_en, "source": d.source,
            "language": d.language, "classification": d.classification, "is_synthetic": d.is_synthetic, "tags": d.tags,
            "current_version": _version(cur) if cur else None, "version_count": len(d.versions), "created_at": d.created_at,
            "updated_at": d.updated_at}


def _get(db: Session, p: Principal, doc_id: uuid.UUID) -> RegulatoryDocument:
    d = db.get(RegulatoryDocument, doc_id)
    if not d or d.org_id != p.org_id or d.deleted_at is not None or d.classification not in p.allowed_classifications():
        raise NotFound("Regulatory document", "الوثيقة التنظيمية")
    return d


@router.get("/regulatory/documents")
def list_docs(p: Principal = Depends(require("regulatory:read")), db: Session = Depends(get_db), q: str = "", classification: str = ""):
    conds = [RegulatoryDocument.org_id == p.org_id, RegulatoryDocument.deleted_at.is_(None),
             RegulatoryDocument.classification.in_(p.allowed_classifications())]
    if q:
        like = f"%{q}%"
        conds.append(RegulatoryDocument.title_ar.ilike(like) | RegulatoryDocument.title_en.ilike(like) | RegulatoryDocument.document_code.ilike(like))
    if classification:
        conds.append(RegulatoryDocument.classification == classification)
    rows = db.scalars(select(RegulatoryDocument).where(*conds).order_by(RegulatoryDocument.document_code)).all()
    hidden = db.scalar(select(func.count()).select_from(RegulatoryDocument).where(
        RegulatoryDocument.org_id == p.org_id, RegulatoryDocument.deleted_at.is_(None),
        RegulatoryDocument.classification.not_in(p.allowed_classifications())))
    return {"items": [_doc(d) for d in rows], "restricted_hidden": hidden or 0}


@router.post("/regulatory/documents", status_code=201)
async def upload(file: UploadFile = File(...), document_code: str = Form(..., min_length=2, max_length=60), title_ar: str = Form(""),
                 title_en: str = Form(""), source: str = Form(""), classification: str = Form("internal"),
                 is_synthetic: bool = Form(True), version_label: str = Form(""), publication_date: date | None = Form(None),
                 effective_date: date | None = Form(None), tags: str = Form(""),
                 p: Principal = Depends(require("regulatory:manage")), db: Session = Depends(get_db)):
    data = await file.read()
    v = ingest_regulatory_document(db, p, filename=file.filename or "upload.txt", data=data, document_code=document_code.strip(),
                                   title_ar=title_ar, title_en=title_en, source=source, classification=classification,
                                   is_synthetic=is_synthetic, version_label=version_label, publication_date=publication_date,
                                   effective_date=effective_date, tags=[t.strip() for t in tags.split(",") if t.strip()])
    return {"document": _doc(db.get(RegulatoryDocument, v.document_id)), "version": _version(v)}


@router.get("/regulatory/documents/{doc_id}")
def doc_detail(doc_id: uuid.UUID, p: Principal = Depends(require("regulatory:read")), db: Session = Depends(get_db)):
    d = _get(db, p, doc_id)
    return {**_doc(d), "versions": [_version(v) for v in d.versions]}


@router.get("/regulatory/documents/{doc_id}/chunks")
def doc_chunks(doc_id: uuid.UUID, version_id: uuid.UUID | None = None, p: Principal = Depends(require("regulatory:read")),
               db: Session = Depends(get_db)):
    d = _get(db, p, doc_id)
    vid = version_id or d.current_version_id
    if not any(v.id == vid for v in d.versions):
        raise NotFound("Version", "الإصدار")
    rows = db.scalars(select(RegulatoryChunk).where(RegulatoryChunk.version_id == vid).order_by(RegulatoryChunk.chunk_index)).all()
    return [{"id": str(c.id), "chunk_index": c.chunk_index, "page_number": c.page_number, "section": c.section,
             "language": c.language, "text": c.text} for c in rows]


@router.get("/regulatory/chunks/{chunk_id}")
def chunk_detail(chunk_id: uuid.UUID, p: Principal = Depends(require("regulatory:read")), db: Session = Depends(get_db)):
    c = db.get(RegulatoryChunk, chunk_id)
    if not c or c.org_id != p.org_id or c.document.classification not in p.allowed_classifications():
        raise NotFound("Passage", "المقطع")
    neighbours = db.scalars(select(RegulatoryChunk).where(RegulatoryChunk.version_id == c.version_id,
                                                          RegulatoryChunk.chunk_index.between(c.chunk_index - 1, c.chunk_index + 1))
                            .order_by(RegulatoryChunk.chunk_index)).all()
    return {"id": str(c.id), "text": c.text, "section": c.section, "page_number": c.page_number, "chunk_index": c.chunk_index,
            "document": _doc(c.document), "version": _version(c.version),
            "context": [{"id": str(n.id), "text": n.text, "section": n.section, "page_number": n.page_number, "is_target": n.id == c.id}
                        for n in neighbours]}


@router.delete("/regulatory/documents/{doc_id}", status_code=204)
def delete_doc(doc_id: uuid.UUID, p: Principal = Depends(require("regulatory:manage")), db: Session = Depends(get_db)):
    from datetime import datetime, timezone

    d = _get(db, p, doc_id)
    d.deleted_at = datetime.now(timezone.utc)
    audit.record(db, category="DOCUMENT", action="regulatory_document_deleted", principal=p, resource_type="regulatory_document",
                 resource_id=d.id)


def _filters(body: SearchIn) -> SearchFilters:
    return SearchFilters(document_ids=body.document_ids, version_id=body.version_id, include_superseded=body.include_superseded,
                         section=body.section, language=body.language, published_from=body.published_from, published_to=body.published_to,
                         effective_from=body.effective_from, effective_to=body.effective_to, tags=body.tags)


@router.post("/regulatory/search")
def search(body: SearchIn, p: Principal = Depends(require("regulatory:read")), db: Session = Depends(get_db)):
    hits, meta = hybrid_search(db, p, body.query, _filters(body), top_k=body.top_k, mode=body.mode, rerank=body.rerank)
    audit.record(db, category="RETRIEVAL", action="regulatory_search", principal=p,
                 details={"query": body.query, "mode": body.mode, "hits": len(hits), "latency_ms": meta["latency_ms"]})
    return {"results": [h.to_dict() for h in hits], "meta": meta}


@router.post("/rag/query")
def rag(body: RagIn, p: Principal = Depends(require("regulatory:read")), db: Session = Depends(get_db)):
    return answer_question(db, p, body.query, _filters(body), locale=body.locale, top_k=min(body.top_k, 8))


# ---- configured requirements --------------------------------------------------------------
def _req(r: RegulatoryRequirement) -> dict:
    return {c.name: getattr(r, c.name) for c in RegulatoryRequirement.__table__.columns if c.name not in ("deleted_at",)}


@router.get("/regulatory/requirements")
def list_requirements(p: Principal = Depends(require("regulatory:read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(RegulatoryRequirement).where(RegulatoryRequirement.org_id == p.org_id, RegulatoryRequirement.deleted_at.is_(None))
                      .order_by(RegulatoryRequirement.code)).all()
    return [_req(r) for r in rows]


@router.post("/regulatory/requirements", status_code=201)
def create_requirement(body: RequirementIn, p: Principal = Depends(require("regulatory:manage")), db: Session = Depends(get_db)):
    if db.scalar(select(RegulatoryRequirement.id).where(RegulatoryRequirement.org_id == p.org_id, RegulatoryRequirement.code == body.code)):
        raise AppError("Requirement code already exists", "رمز المتطلب مستخدم مسبقاً", status_code=409)
    r = RegulatoryRequirement(org_id=p.org_id, **body.model_dump())
    db.add(r)
    db.flush()
    audit.record(db, category="SETTINGS", action="requirement_created", principal=p, resource_type="requirement", resource_id=r.id,
                 details={"code": body.code})
    return _req(r)


@router.patch("/regulatory/requirements/{req_id}")
def update_requirement(req_id: uuid.UUID, body: dict, p: Principal = Depends(require("regulatory:manage")), db: Session = Depends(get_db)):
    r = db.get(RegulatoryRequirement, req_id)
    if not r or r.org_id != p.org_id:
        raise NotFound("Requirement", "المتطلب")
    data = RequirementIn.model_validate({**_req(r), **body}).model_dump()
    for k, v in data.items():
        setattr(r, k, v)
    audit.record(db, category="SETTINGS", action="requirement_updated", principal=p, resource_type="requirement", resource_id=r.id,
                 details={"fields": sorted(body)})
    return _req(r)
