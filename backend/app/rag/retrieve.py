"""Permission- and version-aware hybrid retrieval (keyword + vector, fused with RRF)."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date

import numpy as np
from sqlalchemy import Float, and_, cast, func, literal, select, text
from sqlalchemy.orm import Session

from app.ai.service import get_ai
from app.core.db import pgvector_available
from app.core.security import Principal
from app.models.vector import PgVector
from app.models import Embedding, RegulatoryChunk, RegulatoryDocument, RegulatoryDocumentVersion
from app.rag.normalize import tokenize


@dataclass
class SearchFilters:
    document_ids: list[uuid.UUID] = field(default_factory=list)
    version_id: uuid.UUID | None = None  # explicit version → overrides "active only"
    include_superseded: bool = False
    section: str = ""
    language: str = ""
    published_from: date | None = None
    published_to: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Hit:
    chunk_id: str
    document_id: str
    document_code: str
    title_ar: str
    title_en: str
    source: str
    classification: str
    is_synthetic: bool
    version_id: str
    version_label: str
    version_status: str
    publication_date: str | None
    effective_date: str | None
    page_number: int | None
    section: str
    text: str
    score: float
    keyword_score: float
    vector_score: float
    keyword_rank: int | None
    vector_rank: int | None

    def to_dict(self) -> dict:
        return asdict(self)


def _base_conditions(principal: Principal, f: SearchFilters):
    conds = [
        RegulatoryChunk.org_id == principal.org_id,  # tenant isolation
        RegulatoryDocument.deleted_at.is_(None),
        RegulatoryDocument.classification.in_(principal.allowed_classifications()),  # permission-aware
        RegulatoryDocumentVersion.indexing_status == "INDEXED",
    ]
    if f.version_id:
        conds.append(RegulatoryChunk.version_id == f.version_id)
    elif not f.include_superseded:
        conds.append(RegulatoryDocumentVersion.status == "ACTIVE")  # version-aware
    if f.document_ids:
        conds.append(RegulatoryChunk.document_id.in_(f.document_ids))
    if f.section:
        conds.append(RegulatoryChunk.section.ilike(f"%{f.section}%"))
    if f.language:
        conds.append(RegulatoryChunk.language.in_([f.language, "mixed"]))
    if f.published_from:
        conds.append(RegulatoryDocumentVersion.publication_date >= f.published_from)
    if f.published_to:
        conds.append(RegulatoryDocumentVersion.publication_date <= f.published_to)
    if f.effective_from:
        conds.append(RegulatoryDocumentVersion.effective_date >= f.effective_from)
    if f.effective_to:
        conds.append(RegulatoryDocumentVersion.effective_date <= f.effective_to)
    if f.tags:
        conds.append(RegulatoryDocument.tags.op("?|")(f.tags))
    return conds


def _joined(stmt):
    return stmt.join(RegulatoryDocument, RegulatoryDocument.id == RegulatoryChunk.document_id).join(
        RegulatoryDocumentVersion, RegulatoryDocumentVersion.id == RegulatoryChunk.version_id)


def keyword_search(db: Session, principal: Principal, query: str, f: SearchFilters, limit: int = 30) -> list[tuple[uuid.UUID, float]]:
    toks = list(dict.fromkeys(tokenize(query)))
    if not toks:
        return []
    safe = [t.replace("'", "").replace(":", "").replace("&", "").replace("|", "") for t in toks]
    tsq = func.to_tsquery("simple", " | ".join(f"{t}:*" for t in safe if t))
    rank = func.ts_rank_cd(RegulatoryChunk.search_vector, tsq, 32)
    stmt = _joined(select(RegulatoryChunk.id, rank.label("r"))).where(
        and_(*_base_conditions(principal, f)), RegulatoryChunk.search_vector.op("@@")(tsq)
    ).order_by(text("r DESC")).limit(limit)
    return [(row[0], float(row[1])) for row in db.execute(stmt)]


def vector_search(db: Session, principal: Principal, qvec: list[float], f: SearchFilters, limit: int = 30) -> list[tuple[uuid.UUID, float]]:
    conds = _base_conditions(principal, f)
    if pgvector_available():
        dist = Embedding.vector.op("<=>", return_type=Float())(cast(literal(json.dumps(qvec)), PgVector()))  # cosine distance
        stmt = _joined(select(RegulatoryChunk.id, (1 - dist).label("sim"))).join(
            Embedding, Embedding.chunk_id == RegulatoryChunk.id).where(and_(*conds)).order_by(dist).limit(limit)
        return [(r[0], float(r[1])) for r in db.execute(stmt)]
    # portable fallback: exact cosine in numpy over the permitted candidate set
    stmt = _joined(select(RegulatoryChunk.id, Embedding.vector)).join(Embedding, Embedding.chunk_id == RegulatoryChunk.id).where(and_(*conds))
    rows = db.execute(stmt).all()
    if not rows:
        return []
    ids = [r[0] for r in rows]
    mat = np.asarray([r[1] for r in rows], dtype=np.float32)
    q = np.asarray(qvec, dtype=np.float32)
    sims = mat @ q / ((np.linalg.norm(mat, axis=1) * (np.linalg.norm(q) or 1.0)) + 1e-9)
    order = np.argsort(-sims)[:limit]
    return [(ids[i], float(sims[i])) for i in order]


def lexical_rerank(query: str, hits: list[Hit]) -> list[Hit]:
    """Optional deterministic reranker: rewards query-term coverage within the passage."""
    q = set(tokenize(query))
    if not q:
        return hits
    for h in hits:
        cov = len(q & set(tokenize(h.text + " " + h.section))) / len(q)
        h.score = round(0.7 * h.score + 0.3 * cov, 4)
    return sorted(hits, key=lambda h: -h.score)


def hybrid_search(
    db: Session, principal: Principal, query: str, filters: SearchFilters | None = None, *, top_k: int = 8,
    mode: str = "hybrid", rerank: bool = False,
) -> tuple[list[Hit], dict]:
    f = filters or SearchFilters()
    t0 = time.perf_counter()
    kw: list[tuple[uuid.UUID, float]] = []
    vec: list[tuple[uuid.UUID, float]] = []
    ai = get_ai()
    if mode in ("hybrid", "keyword"):
        kw = keyword_search(db, principal, query, f)
    if mode in ("hybrid", "semantic"):
        vec = vector_search(db, principal, ai.embed([query], purpose="query")[0], f)
    k = 60
    fused: dict[uuid.UUID, float] = {}
    kw_rank = {cid: i + 1 for i, (cid, _) in enumerate(kw)}
    vec_rank = {cid: i + 1 for i, (cid, _) in enumerate(vec)}
    kw_score = dict(kw)
    vec_score = dict(vec)
    for cid in set(kw_rank) | set(vec_rank):
        s = 0.0
        if cid in kw_rank:
            s += 1 / (k + kw_rank[cid])
        if cid in vec_rank:
            s += 1 / (k + vec_rank[cid])
        fused[cid] = s
    # display relevance in [0,1]: blend of normalised components (RRF only orders)
    max_kw = max(kw_score.values(), default=0) or 1.0
    ordered = sorted(fused, key=lambda c: -fused[c])[: max(top_k * 2, top_k)]
    if not ordered:
        return [], {"latency_ms": int((time.perf_counter() - t0) * 1000), "keyword_hits": 0, "vector_hits": 0, "mode": mode}
    rows = db.execute(select(RegulatoryChunk).where(RegulatoryChunk.id.in_(ordered))).scalars().all()
    by_id = {r.id: r for r in rows}
    hits: list[Hit] = []
    for cid in ordered:
        ch = by_id.get(cid)
        if ch is None:
            continue
        vs = max(0.0, vec_score.get(cid, 0.0))
        ks = kw_score.get(cid, 0.0) / max_kw
        if mode == "keyword":
            rel = ks
        elif mode == "semantic":
            rel = vs
        else:
            rel = 0.55 * vs + 0.45 * ks if cid in kw_score else 0.8 * vs
        v = ch.version
        hits.append(Hit(
            chunk_id=str(ch.id), document_id=str(ch.document_id), document_code=ch.document.document_code,
            title_ar=ch.document.title_ar, title_en=ch.document.title_en, source=ch.document.source,
            classification=ch.document.classification, is_synthetic=ch.document.is_synthetic, version_id=str(v.id),
            version_label=v.version_label, version_status=v.status,
            publication_date=v.publication_date.isoformat() if v.publication_date else None,
            effective_date=v.effective_date.isoformat() if v.effective_date else None,
            page_number=ch.page_number, section=ch.section, text=ch.text, score=round(rel, 4),
            keyword_score=round(ks, 4), vector_score=round(vs, 4), keyword_rank=kw_rank.get(cid), vector_rank=vec_rank.get(cid),
        ))
    if rerank:
        hits = lexical_rerank(query, hits)
    hits = hits[:top_k]
    meta = {"latency_ms": int((time.perf_counter() - t0) * 1000), "keyword_hits": len(kw), "vector_hits": len(vec), "mode": mode,
            "vector_backend": "pgvector" if pgvector_available() else "array", "embedding_model": ai.embedder.model,
            "embedding_mock": ai.embedder.is_mock, "reranked": rerank}
    return hits, meta
