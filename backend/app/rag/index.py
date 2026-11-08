"""Regulatory document ingestion: validate → store → extract → normalise → chunk → embed → index."""
from __future__ import annotations

import hashlib
import logging
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.ai.service import get_ai
from app.core.config import settings
from app.core.db import pgvector_available
from app.core.errors import AppError
from app.core.security import Principal
from app.models import Embedding, RegulatoryChunk, RegulatoryDocument, RegulatoryDocumentVersion
from app.rag.chunk import chunk_blocks
from app.rag.extract import extract, validate_file
from app.rag.normalize import detect_language, tokenize
from app.services import audit
from app.services.storage import get_storage, new_key, scan_bytes

log = logging.getLogger("rip.rag.index")


def index_text(text: str) -> str:
    """The keyword index stores stemmed, stopword-free tokens so Arabic morphology matches."""
    return " ".join(tokenize(text))


def ingest_regulatory_document(
    db: Session,
    principal: Principal,
    *,
    filename: str,
    data: bytes,
    document_code: str,
    title_ar: str = "",
    title_en: str = "",
    source: str = "",
    classification: str = "internal",
    is_synthetic: bool = True,
    version_label: str = "",
    publication_date: date | None = None,
    effective_date: date | None = None,
    tags: list[str] | None = None,
) -> RegulatoryDocumentVersion:
    content_type = validate_file(filename, data, settings.max_upload_mb)
    scan = scan_bytes(data)
    if scan.status == "INFECTED":
        raise AppError("File failed malware scanning", "لم يجتز الملف فحص البرمجيات الضارة", status_code=422, code="INFECTED_FILE")
    if classification not in ("public", "internal", "restricted"):
        raise AppError("Invalid classification", "تصنيف غير صالح", status_code=422)

    doc = db.scalar(select(RegulatoryDocument).where(
        RegulatoryDocument.org_id == principal.org_id, RegulatoryDocument.document_code == document_code,
        RegulatoryDocument.deleted_at.is_(None)))
    if doc is None:
        doc = RegulatoryDocument(org_id=principal.org_id, document_code=document_code, title_ar=title_ar, title_en=title_en,
                                 source=source, classification=classification, is_synthetic=is_synthetic, tags=tags or [])
        db.add(doc)
        db.flush()
    else:
        doc.title_ar = title_ar or doc.title_ar
        doc.title_en = title_en or doc.title_en
        doc.source = source or doc.source
        doc.classification = classification
        doc.is_synthetic = is_synthetic

    sha = hashlib.sha256(data).hexdigest()
    next_no = (db.scalar(select(func.max(RegulatoryDocumentVersion.version_number))
                         .where(RegulatoryDocumentVersion.document_id == doc.id)) or 0) + 1
    key = get_storage().put(new_key(principal.org_id, "regulatory", filename), data)
    version = RegulatoryDocumentVersion(
        org_id=principal.org_id, document_id=doc.id, version_number=next_no, version_label=version_label or f"v{next_no}",
        publication_date=publication_date, effective_date=effective_date, filename=filename, content_type=content_type,
        sha256=sha, storage_key=key, indexing_status="PENDING",
    )
    db.add(version)
    db.flush()

    try:
        ex = extract(filename, data)
        chunks = chunk_blocks(ex.blocks)
        if not chunks:
            raise AppError("No extractable text found", "لم يُعثر على نص قابل للاستخراج", status_code=422)
        lang = detect_language(ex.full_text)
        doc.language = lang if lang != "unknown" else doc.language
        if not doc.title_ar and not doc.title_en and ex.metadata.get("title"):
            doc.title_en = ex.metadata["title"]
        ai = get_ai()
        vectors = ai.embed([c.text for c in chunks], purpose="index_regulatory")
        rows = []
        for c, vec in zip(chunks, vectors):
            ch = RegulatoryChunk(org_id=principal.org_id, document_id=doc.id, version_id=version.id, chunk_index=c.index,
                                 page_number=c.page, section=c.section[:300], language=c.language, text=c.text,
                                 normalized_text=index_text(c.text), token_count=len(c.text) // 4)
            db.add(ch)
            rows.append((ch, vec))
        db.flush()
        for ch, vec in rows:
            db.add(Embedding(org_id=principal.org_id, chunk_id=ch.id, provider=ai.embedder.name, model=ai.embedder.model,
                             dim=len(vec), vector=vec))
        # version-awareness: the new version becomes ACTIVE, older ones SUPERSEDED
        db.execute(update(RegulatoryDocumentVersion).where(
            RegulatoryDocumentVersion.document_id == doc.id, RegulatoryDocumentVersion.id != version.id
        ).values(status="SUPERSEDED"))
        version.status = "ACTIVE"
        version.page_count = len(ex.pages)
        version.chunk_count = len(chunks)
        version.indexing_status = "INDEXED"
        version.extracted_metadata = {
            "language": lang, "paginated": ex.metadata.get("paginated", True), "sections": len({c.section for c in chunks}),
            "embedding_provider": ai.embedder.name, "embedding_model": ai.embedder.model, "embedding_mock": ai.embedder.is_mock,
            "vector_backend": "pgvector" if pgvector_available() else "array", "scan_status": scan.status,
        }
        doc.current_version_id = version.id
    except AppError:
        raise
    except Exception as e:  # recorded, never swallowed silently
        log.exception("indexing failed")
        version.indexing_status = "FAILED"
        version.indexing_error = str(e)[:1000]
        raise AppError(f"Indexing failed: {e}", "تعذرت فهرسة الوثيقة", status_code=422, code="INDEXING_FAILED") from e

    audit.record(db, category="DOCUMENT", action="regulatory_document_indexed", principal=principal,
                 resource_type="regulatory_document_version", resource_id=version.id,
                 details={"document_code": document_code, "version": version.version_label, "chunks": version.chunk_count,
                          "scan": scan.status})
    return version
