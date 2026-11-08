"""Grounded answer generation with citation validation and insufficient-evidence handling."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai import guard
from app.ai.service import get_ai
from app.core.config import settings
from app.core.security import Principal
from app.rag.chunk import split_sentences
from app.rag.normalize import normalize, tokenize
from app.rag.retrieve import Hit, SearchFilters, hybrid_search
from app.services import audit


class CitedQuote(BaseModel):
    source_id: str = Field(description="One of the supplied ids, e.g. S1")
    quote: str = Field(description="Exact supporting sentence copied from that source")


class RagAnswer(BaseModel):
    insufficient_evidence: bool = False
    evidence_summary: str = Field(default="", description="What the sources say (facts only)")
    interpretation: str = Field(default="", description="Model interpretation, clearly separate from evidence")
    citations: list[CitedQuote] = Field(default_factory=list)


def quote_supported(quote: str, chunk_text: str) -> bool:
    """A quote is verified when it appears (normalised) in the chunk, or ≥85% of its tokens do."""
    nq, nc = normalize(quote), normalize(chunk_text)
    if len(nq) >= 12 and nq in nc:
        return True
    qt = tokenize(quote)
    if len(qt) < 3:
        return False
    ct = set(tokenize(chunk_text))
    return sum(1 for t in qt if t in ct) / len(qt) >= 0.85


def best_sentences(query: str, hit: Hit, n: int = 2) -> list[str]:
    q = set(tokenize(query))
    sents = [s for s in split_sentences(hit.text) if len(s) > 15 and s.strip() != (hit.section or "").strip()]
    scored = sorted(sents, key=lambda s: -len(q & set(tokenize(s))))
    return [s for s in scored[:n] if q & set(tokenize(s))] or sents[:1]


def build_context(hits: list[Hit]) -> tuple[str, dict[str, Hit]]:
    by_id: dict[str, Hit] = {}
    parts = []
    for i, h in enumerate(hits, 1):
        sid = f"S{i}"
        by_id[sid] = h
        src = f"{h.document_code} {h.version_label} | {h.section} | page {h.page_number or '-'}"
        parts.append(guard.wrap(sid, h.text, src))
    return "\n\n".join(parts), by_id


def answer_question(db: Session, principal: Principal, question: str, filters: SearchFilters | None = None,
                    locale: str = "ar", top_k: int | None = None) -> dict:
    ai = get_ai()
    hits, meta = hybrid_search(db, principal, question, filters, top_k=top_k or settings.rag_top_k, rerank=True)
    q_scan = guard.scan(question)
    relevant = [h for h in hits if h.score >= settings.rag_min_score]
    base = {"question": question, "retrieval": meta, "sources": [h.to_dict() for h in hits], "provider": ai.cfg.public(),
            "is_mock": ai.is_mock, "query_injection_flags": q_scan.matches}

    if not relevant:
        audit.record(db, category="RETRIEVAL", action="rag_query", principal=principal,
                     details={"question": question, "hits": len(hits), "insufficient": True})
        return {**base, "insufficient_evidence": True, "evidence_summary": "", "interpretation": "",
                "message_ar": "لا تتوفر أدلة كافية في قاعدة المعرفة للإجابة عن هذا السؤال.",
                "message_en": "The knowledge base does not contain sufficient evidence to answer this question.",
                "citations": [], "citation_accuracy": None}

    context, by_id = build_context(relevant)
    injected = {sid: guard.scan(h.text).matches for sid, h in by_id.items() if guard.scan(h.text).flagged}
    lang_instr = "Answer in Arabic." if locale == "ar" else "Answer in English."
    messages = [
        {"role": "system", "content": guard.SYSTEM_POLICY_EN + " " + guard.SYSTEM_POLICY_AR},
        {"role": "user", "content": f"{lang_instr}\nQuestion: {question}\n\nSources:\n{context}\n\n"
                                    "Return evidence_summary, interpretation, citations (exact quotes) and "
                                    "insufficient_evidence=true if the sources do not answer the question."},
    ]

    def mock_builder() -> dict:
        cits, summary = [], []
        for sid, h in list(by_id.items())[:3]:
            for s in best_sentences(question, h, 1):
                cits.append({"source_id": sid, "quote": s})
                summary.append(f"{s} [{sid}]")
        interp = ("ملخص استخراجي للنصوص الأكثر صلة من المصادر المفهرسة. يُرجع إلى النص الرسمي قبل الاعتماد."
                  if locale == "ar" else
                  "Extractive summary of the most relevant indexed passages. Verify against the official text before reliance.")
        return {"insufficient_evidence": False, "evidence_summary": "\n".join(summary), "interpretation": interp, "citations": cits}

    parsed, res = ai.structured(messages, RagAnswer, purpose="rag_answer", mock_builder=mock_builder)

    # --- citation validation: ids must be supplied, quotes must exist in the cited chunk ---
    validated = []
    for c in parsed.citations:
        h = by_id.get(c.source_id)
        ok = bool(h) and quote_supported(c.quote, h.text)
        validated.append({"source_id": c.source_id, "quote": c.quote, "verified": ok,
                          "chunk_id": h.chunk_id if h else None, "document_code": h.document_code if h else None,
                          "page_number": h.page_number if h else None, "section": h.section if h else None,
                          "version_label": h.version_label if h else None})
    verified = [v for v in validated if v["verified"]]
    accuracy = round(len(verified) / len(validated), 3) if validated else None
    summary = parsed.evidence_summary
    unsupported = False
    if not parsed.insufficient_evidence and not verified:
        unsupported = True  # protection against unsupported answers
    # remove references to unknown source ids from the text
    summary = re.sub(r"\[(S\d+)\]", lambda m: m.group(0) if m.group(1) in by_id else "", summary)

    audit.record(db, category="RETRIEVAL", action="rag_query", principal=principal,
                 details={"question": question, "hits": len(hits), "citations": len(validated), "verified": len(verified),
                          "model": res.model, "mock": res.is_mock, "injection_flags": list(injected)})
    out = {**base, "insufficient_evidence": parsed.insufficient_evidence or unsupported,
           "evidence_summary": "" if unsupported else summary,
           "interpretation": "" if unsupported else parsed.interpretation,
           "citations": validated, "citation_accuracy": accuracy, "document_injection_flags": injected,
           "model": res.model, "tokens_in": res.tokens_in, "tokens_out": res.tokens_out}
    if unsupported:
        out["message_ar"] = "تعذر التحقق من استشهادات الإجابة، لذلك لم تُعرض."
        out["message_en"] = "The generated answer could not be verified against its citations and was withheld."
    return out
