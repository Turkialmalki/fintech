"""Repeatable RAG evaluation over a versioned dataset (app/seed/data/rag_eval.json).

Metrics: retrieval precision@k, recall@k, MRR, context relevance, groundedness, answer relevance
and citation correctness. With the mock embedder/LLM the numbers measure the pipeline (lexical
retrieval + extractive answers), not a language model — results are stored with is_mock=True.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.service import get_ai
from app.core.security import Principal
from app.models import ModelEvaluation
from app.rag.answer import answer_question
from app.rag.chunk import split_sentences
from app.rag.normalize import tokenize
from app.rag.retrieve import hybrid_search

DATASET = Path(__file__).resolve().parent.parent / "seed" / "data" / "rag_eval.json"


def _relevant(hit: dict, case: dict) -> bool:
    if hit["document_code"] != case["document_code"]:
        return False
    return any(s.lower() in (hit["section"] or "").lower() for s in case["sections"])


def _overlap(a: str, b: str) -> float:
    ta, tb = set(tokenize(a)), set(tokenize(b))
    return len(ta & tb) / len(ta) if ta else 0.0


def run_evaluation(db: Session, principal: Principal, k: int = 5, with_answers: bool = True) -> ModelEvaluation:
    ai = get_ai()
    cases = json.loads(DATASET.read_text(encoding="utf-8"))["cases"]
    details, P, R, MRR, CTX, GND, ANS, CIT, LAT = [], [], [], [], [], [], [], [], []
    for case in cases:
        t0 = time.perf_counter()
        hits, _ = hybrid_search(db, principal, case["question"], top_k=k)
        LAT.append((time.perf_counter() - t0) * 1000)
        hd = [h.to_dict() for h in hits]
        rel = [_relevant(h, case) for h in hd]
        expected = max(1, case.get("expected_relevant", 1))
        P.append(sum(rel) / k)
        R.append(min(1.0, sum(rel) / expected))
        MRR.append(next((1 / (i + 1) for i, r in enumerate(rel) if r), 0.0))
        CTX.append(sum(_overlap(case["question"], h["text"]) for h in hd[:3]) / max(1, min(3, len(hd))))
        row = {"id": case["id"], "language": case["language"], "precision": P[-1], "recall": R[-1], "rr": MRR[-1],
               "top": [f"{h['document_code']}|{h['section']}" for h in hd[:3]]}
        if with_answers:
            ans = answer_question(db, principal, case["question"], locale=case["language"], top_k=k)
            text = ans.get("evidence_summary", "")
            sents = [s for s in split_sentences(text) if len(s) > 10]
            sources = " ".join(h["text"] for h in ans["sources"])
            grounded = sum(1 for s in sents if _overlap(s, sources) >= 0.6) / len(sents) if sents else 0.0
            cits = ans.get("citations", [])
            correct = [c for c in cits if c["verified"] and c["document_code"] == case["document_code"]]
            GND.append(grounded)
            ANS.append(_overlap(case["question"], text))
            CIT.append(len(correct) / len(cits) if cits else 0.0)
            row.update({"groundedness": grounded, "citation_correctness": CIT[-1], "insufficient": ans["insufficient_evidence"]})
        details.append(row)

    def avg(x):
        return round(sum(x) / len(x), 4) if x else None

    metrics = {"precision_at_k": avg(P), "recall_at_k": avg(R), "mrr": avg(MRR), "context_relevance": avg(CTX),
               "groundedness": avg(GND), "answer_relevance": avg(ANS), "citation_correctness": avg(CIT), "k": k,
               "retrieval_latency_ms_avg": avg(LAT),
               "by_language": {lang: {"precision_at_k": avg([d["precision"] for d in details if d["language"] == lang]),
                                      "recall_at_k": avg([d["recall"] for d in details if d["language"] == lang]),
                                      "mrr": avg([d["rr"] for d in details if d["language"] == lang])} for lang in ("ar", "en")}}
    ev = ModelEvaluation(org_id=principal.org_id, provider=ai.cfg.provider, model_name=f"{ai.llm.model} + {ai.embedder.model}",
                         dataset=f"rag_eval.json ({len(cases)} cases)", language="mixed", metrics=metrics, sample_count=len(cases),
                         is_mock=ai.is_mock or ai.embedder.is_mock, details=details, run_by_id=principal.user_id)
    db.add(ev)
    db.flush()
    return ev
