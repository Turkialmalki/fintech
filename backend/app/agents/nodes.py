"""The six agents of the assessment workflow.

Mandatory checks (required documents, configured requirement rules, risk rules) are
deterministic tools. Agents use the model only where context helps: structuring extracted data,
phrasing evidence-linked findings, and summarising. Every agent reaches data through MCP tools.
"""
from __future__ import annotations

import json
import time
from typing import Any, TypedDict

from pydantic import BaseModel, Field

from app.agents.runtime import AgentToolClient, Budget, StepRecorder
from app.ai import guard
from app.ai.service import AIService
from app.rag.answer import best_sentences
from app.rag.retrieve import Hit
from app.services.rules import extract_profile, overall_risk


class AState(TypedDict, total=False):
    run_id: str
    application_id: str
    locale: str
    application: dict
    documents: list[dict]
    profile: dict
    profile_meta: dict
    missing_data: list[str]
    injection_flags: list[dict]
    evidence: list[dict]
    regulatory_findings: list[dict]
    gap_findings: list[dict]
    risk_findings: list[dict]
    required_docs: dict
    draft_id: str
    draft_version: int
    review_status: str
    notes: list[str]


class Ctx:
    """Per-run dependencies handed to every node (kept out of the serialisable state)."""

    def __init__(self, tools: AgentToolClient, ai: AIService, recorder: StepRecorder, budget: Budget):
        self.tools, self.ai, self.recorder, self.budget = tools, ai, recorder, budget
        self.search_cache: dict[str, list[dict]] = {}

    def llm_step(self, agent: str, name: str, res, t0: float, extra: dict | None = None):
        self.budget.tokens += res.tokens_in + res.tokens_out
        self.recorder.record(agent, "LLM_CALL", name, duration_ms=int((time.perf_counter() - t0) * 1000),
                             tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                             output={"model": res.model, "provider": res.provider, "mock": res.is_mock, **(extra or {})})
        self.budget.check()

    async def search(self, agent: str, query: str, top_k: int = 4, document_code: str | None = None) -> list[dict]:
        key = f"{query}|{top_k}|{document_code}"
        if key not in self.search_cache:
            args: dict[str, Any] = {"query": query, "top_k": top_k}
            if document_code:
                args["document_code"] = document_code
            res = await self.tools.call(agent, "search_regulations", args)
            self.search_cache[key] = res["results"]
        return self.search_cache[key]


AGENT_TOOLS: dict[str, set[str]] = {
    "orchestrator": {"get_fintech_application", "get_assessment_history", "submit_for_human_review"},
    "document_intelligence": {"list_application_documents", "get_fintech_application"},
    "regulatory_research": {"search_regulations", "get_regulation_details"},
    "compliance_gap": {"check_required_documents", "analyze_application", "search_regulations"},
    "risk_analysis": {"get_risk_indicators", "search_regulations"},
    "assessment_reporting": {"create_assessment_draft"},
}


def _hit(d: dict) -> Hit:
    fields = Hit.__dataclass_fields__
    return Hit(**{k: d.get(k) for k in fields})


def _cite(h: dict, quote: str) -> dict:
    return {"source_type": "REGULATORY", "chunk_id": h["chunk_id"], "quote": quote, "score": h.get("score", 0)}


# ---------------------------------------------------------------------------------- 1
class ExtractedProfileLLM(BaseModel):
    commercial_registration: str | None = None
    paid_up_capital_sar: float | None = None
    projected_growth_pct: float | None = None
    has_compliance_officer: bool | None = None
    has_mlro: bool | None = None
    data_hosting_mention: str | None = None
    employees: int | None = None
    key_products: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


async def document_intelligence(state: AState, ctx: Ctx) -> AState:
    agent = "document_intelligence"
    t0 = time.perf_counter()
    docs = (await ctx.tools.call(agent, "list_application_documents",
                                 {"application_id": state["application_id"], "include_text": True, "max_chars_per_document": 6000}))["documents"]
    texts = [d.get("text", "") for d in docs if d.get("processing_status") == "PROCESSED"]
    deterministic = extract_profile(texts)
    flags = []
    for d in docs:
        s = guard.scan(d.get("text", ""))
        if s.flagged:
            flags.append({"document_id": d["id"], "filename": d["filename"], "matches": s.matches})
    wrapped = "\n\n".join(guard.wrap(f"D{i + 1}", d.get("text", "")[:6000], d["filename"]) for i, d in enumerate(docs) if d.get("text"))
    app = state["application"]
    expected = ["commercial_registration", "paid_up_capital_sar", "has_compliance_officer", "has_mlro", "data_hosting_mention"]

    def mock_builder() -> dict:
        missing = [k for k in expected if deterministic.get(k) is None and not app.get(k if k != "data_hosting_mention" else "data_hosting_location")]
        return {**{k: deterministic.get(k) for k in ExtractedProfileLLM.model_fields if k in deterministic},
                "key_products": [], "missing_information": missing}

    messages = [{"role": "system", "content": guard.SYSTEM_POLICY_EN},
                {"role": "user", "content": "Extract the applicant profile fields from these applicant-supplied documents. "
                                            "Use null when a value is not explicitly stated; never guess.\n\n" + wrapped}]
    parsed, res = ctx.ai.structured(messages, ExtractedProfileLLM, purpose="document_intelligence", mock_builder=mock_builder)
    ctx.llm_step(agent, "extract_profile", res, t0)
    llm = parsed.model_dump()
    profile: dict[str, Any] = {}
    discrepancies = []
    for k, v in llm.items():
        if k in ("missing_information", "key_products"):
            continue
        dv = deterministic.get(k)
        if dv is not None and v is not None and dv != v:
            discrepancies.append({"field": k, "rule_value": dv, "model_value": v})
        profile[k] = dv if dv is not None else v  # deterministic extraction wins on conflict
    profile = {k: v for k, v in profile.items() if v is not None}
    if app.get("paid_up_capital_sar") and profile.get("paid_up_capital_sar") and \
            abs(float(app["paid_up_capital_sar"]) - float(profile["paid_up_capital_sar"])) > 1:
        discrepancies.append({"field": "paid_up_capital_sar", "application_value": app["paid_up_capital_sar"],
                              "document_value": profile["paid_up_capital_sar"]})
    ctx.recorder.record(agent, "NODE", "document_intelligence", duration_ms=int((time.perf_counter() - t0) * 1000),
                        output={"profile": profile, "discrepancies": discrepancies, "injection_flags": flags})
    return {"documents": [{k: v for k, v in d.items() if k != "text"} for d in docs], "profile": profile,
            "profile_meta": {"discrepancies": discrepancies, "llm_mock": res.is_mock, "key_products": llm.get("key_products", [])},
            "missing_data": parsed.missing_information, "injection_flags": flags}


# ---------------------------------------------------------------------------------- 2
TOPICS: dict[str, list[tuple[str, str, str]]] = {
    "_common": [
        ("capital", "متطلبات رأس المال المدفوع", "Paid-up capital requirements"),
        ("governance", "الحوكمة والهيكل التنظيمي مسؤول الالتزام", "Governance structure and compliance officer"),
        ("aml", "مكافحة غسل الأموال وتمويل الإرهاب اعرف عميلك", "Anti-money laundering and KYC"),
        ("cyber", "سياسة الأمن السيبراني والاستجابة للحوادث", "Cybersecurity policy and incident response"),
        ("data", "حماية البيانات الشخصية واستضافة البيانات داخل المملكة", "Personal data protection and data hosting"),
        ("consumer", "حماية العملاء والإفصاح عن الرسوم ومعالجة الشكاوى", "Consumer protection, fee disclosure, complaints"),
    ],
    "BNPL": [("affordability", "affordability assessment before granting instalment plan", "BNPL affordability assessment"),
             ("bnpl_fees", "late payment charges disclosed fees", "BNPL late payment charges")],
    "OPEN_BANKING": [("consent", "موافقة العميل على الوصول إلى بيانات الحسابات", "Customer consent for account data"),
                     ("api", "أمن واجهات البرمجة والتشفير", "API security and encryption")],
    "DIGITAL_WALLET": [("outsourcing", "الإسناد إلى أطراف خارجية", "Outsourcing to third parties")],
    "DIGITAL_PAYMENTS": [("outsourcing", "الإسناد إلى أطراف خارجية", "Outsourcing to third parties")],
    "LENDING": [("risk", "إطار إدارة المخاطر مخاطر الائتمان", "Credit risk management framework")],
}


class ResearchFinding(BaseModel):
    topic: str
    source_id: str
    quote: str
    title_ar: str
    title_en: str
    interpretation_ar: str
    interpretation_en: str
    uncertainty: str = ""


class ResearchOutput(BaseModel):
    findings: list[ResearchFinding] = Field(default_factory=list)


async def regulatory_research(state: AState, ctx: Ctx) -> AState:
    agent = "regulatory_research"
    t0 = time.perf_counter()
    cat = state["application"]["service_category"]
    topics = TOPICS["_common"] + TOPICS.get(cat, [])
    evidence: list[dict] = []
    supplied: dict[str, dict] = {}
    for key, q_ar, q_en in topics:
        hits = await ctx.search(agent, q_ar, top_k=3)
        if not hits:
            hits = await ctx.search(agent, q_en, top_k=3)
        good = [h for h in hits if h["score"] >= 0.15][:2]
        for h in good:
            sid = f"S{len(supplied) + 1}"
            supplied[sid] = {**h, "topic": key, "query": q_ar}
        evidence.append({"topic": key, "query": q_ar, "hits": [{"chunk_id": h["chunk_id"], "document_code": h["document_code"],
                                                               "section": h["section"], "score": h["score"]} for h in good]})
    context = "\n\n".join(guard.wrap(sid, h["text"], f"{h['document_code']} | {h['section']} | topic={h['topic']}")
                          for sid, h in supplied.items())

    def mock_builder() -> dict:
        out, seen = [], set()
        for sid, h in supplied.items():
            if h["topic"] in seen:
                continue
            seen.add(h["topic"])
            quote = best_sentences(h["query"], _hit(h), 1)[0]
            sec = h["section"] or h["document_code"]
            out.append({"topic": h["topic"], "source_id": sid, "quote": quote,
                        "title_ar": f"متطلب قد ينطبق: {sec}", "title_en": f"Potentially applicable requirement: {sec}",
                        "interpretation_ar": f"[محاكاة] وردت هذه الفقرة ضمن نتائج البحث لموضوع «{h['query']}» وقد تنطبق على فئة الخدمة المقدَّم لها. يلزم تحقق المحلل من الانطباق.",
                        "interpretation_en": f"[Mock] This passage was retrieved for the topic '{h['topic']}' and may apply to the service category ({cat}). Analyst must confirm applicability.",
                        "uncertainty": "Applicability determined by retrieval relevance only (no model reasoning)."})
        return {"findings": out}

    messages = [{"role": "system", "content": guard.SYSTEM_POLICY_EN},
                {"role": "user", "content": f"Service category: {cat}. For each topic, identify the passage that states a potentially "
                                            "applicable requirement. Copy an exact quote, cite its source id, give a short title "
                                            "and an interpretation in Arabic and English, and state uncertainty.\n\n" + context}]
    parsed, res = ctx.ai.structured(messages, ResearchOutput, purpose="regulatory_research", mock_builder=mock_builder)
    ctx.llm_step(agent, "evidence_linked_findings", res, t0)
    findings = []
    dropped = 0
    for f in parsed.findings:
        h = supplied.get(f.source_id)
        if h is None:  # model cited an id we never supplied → drop
            dropped += 1
            continue
        findings.append({"category": "REGULATORY", "severity": "INFO", "title_ar": f.title_ar, "title_en": f.title_en,
                         "evidence_ar": f.quote, "evidence_en": f.quote, "interpretation_ar": f.interpretation_ar,
                         "interpretation_en": f.interpretation_en, "uncertainty": f.uncertainty, "source_agent": agent,
                         "origin": "AI", "citations": [_cite(h, f.quote)]})
    ctx.recorder.record(agent, "NODE", "regulatory_research", duration_ms=int((time.perf_counter() - t0) * 1000),
                        output={"topics": len(topics), "passages": len(supplied), "findings": len(findings), "dropped_invalid_citations": dropped})
    return {"evidence": evidence, "regulatory_findings": findings}


# ---------------------------------------------------------------------------------- 3
async def compliance_gap(state: AState, ctx: Ctx) -> AState:
    agent = "compliance_gap"
    t0 = time.perf_counter()
    aid = state["application_id"]
    req_docs = await ctx.tools.call(agent, "check_required_documents", {"application_id": aid})
    analysis = await ctx.tools.call(agent, "analyze_application", {"application_id": aid})
    findings = []
    for r in analysis["requirements"]:
        if r["outcome"] == "MET":
            continue
        cits = []
        if r["source_document_code"]:
            hits = await ctx.search(agent, r["title_ar"] + " " + r["source_section"], top_k=2, document_code=r["source_document_code"])
            for h in hits[:1]:
                cits.append(_cite(h, best_sentences(r["title_ar"], _hit(h), 1)[0]))
        gap = r["outcome"] == "POTENTIAL_GAP"
        findings.append({
            "category": "GAP" if gap else "MISSING_INFORMATION", "severity": r["severity"] if gap else "MEDIUM",
            "title_ar": ("فجوة محتملة: " if gap else "معلومات غير مكتملة: ") + r["title_ar"],
            "title_en": ("Potential gap: " if gap else "Insufficient information: ") + r["title_en"],
            "evidence_ar": f"نتيجة الفحص الآلي للمتطلب {r['code']}: {r['detail']}",
            "evidence_en": f"Deterministic check of {r['code']}: {r['detail']}",
            "interpretation_ar": "فجوة محتملة بناءً على المتطلبات المهيأة في النظام (اصطناعية)، وتتطلب تأكيد المحلل.",
            "interpretation_en": "Potential gap against configured (synthetic) requirements; requires analyst confirmation.",
            "uncertainty": "Rule-based; depends on completeness of submitted data.", "source_agent": agent, "origin": "RULE",
            "requirement_code": r["code"], "citations": cits})
    ctx.recorder.record(agent, "NODE", "compliance_gap", duration_ms=int((time.perf_counter() - t0) * 1000),
                        output={"missing_documents": [m["document_type"] for m in req_docs["missing"]], "summary": analysis["summary"]})
    return {"required_docs": req_docs, "gap_findings": findings}


# ---------------------------------------------------------------------------------- 4
async def risk_analysis(state: AState, ctx: Ctx) -> AState:
    agent = "risk_analysis"
    t0 = time.perf_counter()
    res = await ctx.tools.call(agent, "get_risk_indicators", {"application_id": state["application_id"]})
    findings = []
    for ind in res["indicators"]:
        cits = []
        if ind.get("evidence_query"):
            hits = await ctx.search(agent, ind["evidence_query"], top_k=2)
            if hits and hits[0]["score"] >= 0.15:
                cits.append(_cite(hits[0], best_sentences(ind["evidence_query"], _hit(hits[0]), 1)[0]))
        if ind.get("document_id"):
            cits.append({"source_type": "APPLICATION_DOCUMENT", "application_document_id": ind["document_id"],
                         "quote": "; ".join(ind["observed_value"]) if isinstance(ind["observed_value"], list) else str(ind["observed_value"])})
        findings.append({
            "category": "RISK", "severity": ind["severity"], "title_ar": ind["title_ar"], "title_en": ind["title_en"],
            "evidence_ar": f"القيمة المرصودة: {json.dumps(ind['observed_value'], ensure_ascii=False)} — القاعدة: {ind['rule']}",
            "evidence_en": f"Observed value: {json.dumps(ind['observed_value'], ensure_ascii=False)} — rule: {ind['rule']}",
            "interpretation_ar": "مؤشر مخاطر محتمل وفق قواعد قابلة للتهيئة؛ لا يعني بذاته عدم الامتثال.",
            "interpretation_en": "Potential risk indicator under configurable rules; not by itself a finding of non-compliance.",
            "uncertainty": "Severity taken from configured rule categories.", "source_agent": agent, "origin": "RULE",
            "requirement_code": ind["code"], "citations": cits})
    for disc in state.get("profile_meta", {}).get("discrepancies", []):
        findings.append({
            "category": "OBSERVATION", "severity": "MEDIUM",
            "title_ar": f"تباين بين بيانات الطلب والوثائق في الحقل {disc['field']}",
            "title_en": f"Mismatch between application data and documents for {disc['field']}",
            "evidence_ar": json.dumps(disc, ensure_ascii=False), "evidence_en": json.dumps(disc, ensure_ascii=False),
            "interpretation_ar": "قد يشير إلى خطأ إدخال أو وثائق غير محدثة.", "interpretation_en": "May indicate a data-entry error or outdated documents.",
            "uncertainty": "Extraction may be imperfect.", "source_agent": agent, "origin": "AI", "citations": []})
    ctx.recorder.record(agent, "NODE", "risk_analysis", duration_ms=int((time.perf_counter() - t0) * 1000),
                        output={"indicators": [i["code"] for i in res["indicators"]]})
    return {"risk_findings": findings}


# ---------------------------------------------------------------------------------- 5
class ReportSummary(BaseModel):
    summary_ar: str
    summary_en: str


LIMITATIONS_AR = ("هذا تقييم أولي آلي لدعم المحلل وليس قراراً تنظيمياً أو قرار ترخيص. جميع الوثائق التنظيمية في بيئة العرض اصطناعية. "
                  "قد تكون عملية الاستخراج والبحث غير مكتملة، ويجب التحقق من كل دليل قبل الاعتماد.")
LIMITATIONS_EN = ("This is a preliminary, automated assessment to support an analyst. It is not a regulatory or licensing decision. "
                  "All regulatory documents in the demo environment are synthetic. Extraction and retrieval may be incomplete; "
                  "every piece of evidence must be verified before reliance.")


async def assessment_reporting(state: AState, ctx: Ctx) -> AState:
    agent = "assessment_reporting"
    t0 = time.perf_counter()
    findings = state.get("gap_findings", []) + state.get("risk_findings", []) + state.get("regulatory_findings", [])
    risk_levels = [f["severity"] for f in findings if f["category"] in ("RISK", "GAP")]
    level = overall_risk(risk_levels)
    app = state["application"]
    missing = state.get("required_docs", {}).get("missing", [])
    counts = {c: sum(1 for f in findings if f["category"] == c) for c in ("REGULATORY", "GAP", "MISSING_INFORMATION", "RISK", "OBSERVATION")}

    cat_ar = {"BNPL": "الشراء الآن والدفع لاحقاً", "DIGITAL_PAYMENTS": "المدفوعات الرقمية", "OPEN_BANKING": "المصرفية المفتوحة",
              "LENDING": "التمويل الرقمي", "DIGITAL_WALLET": "المحافظ الرقمية"}.get(app["service_category"], app["service_category"])
    risk_ar = {"CRITICAL": "حرج", "HIGH": "مرتفع", "MEDIUM": "متوسط", "LOW": "منخفض"}.get(level, level)
    cat_en = app["service_category"].replace("_", " ").title()

    def mock_builder() -> dict:
        return {
            "summary_ar": (f"[ملخص آلي — وضع المحاكاة] أُجري تقييم أولي لطلب {app['company_name_ar']} ({app['reference']}) ضمن فئة {cat_ar}. "
                           f"رُصدت {counts['GAP']} فجوات محتملة و{counts['MISSING_INFORMATION']} حالات نقص معلومات و{counts['RISK']} مؤشرات مخاطر، "
                           f"مع {counts['REGULATORY']} متطلبات قد تنطبق. عدد الوثائق الناقصة: {len(missing)}. مستوى المخاطر الأولي: {risk_ar}. "
                           "يتطلب التقييم مراجعة بشرية قبل أي إجراء."),
            "summary_en": (f"[Automated summary — mock mode] Preliminary assessment of {app['company_name_en']} ({app['reference']}), category "
                           f"{cat_en}: {counts['GAP']} potential gaps, {counts['MISSING_INFORMATION']} information gaps, "
                           f"{counts['RISK']} risk indicators and {counts['REGULATORY']} potentially applicable requirements. "
                           f"Missing documents: {len(missing)}. Preliminary risk level: {level}. Human review is required before any action."),
        }

    digest = json.dumps([{k: f[k] for k in ("category", "severity", "title_en")} for f in findings], ensure_ascii=False)
    messages = [{"role": "system", "content": guard.SYSTEM_POLICY_EN},
                {"role": "user", "content": f"Write a neutral 4-sentence preliminary summary in Arabic and English. Use only these "
                                            f"validated findings; do not add requirements or decisions. Overall preliminary risk: {level}.\n{digest}"}]
    parsed, res = ctx.ai.structured(messages, ReportSummary, purpose="assessment_reporting", mock_builder=mock_builder)
    ctx.llm_step(agent, "summarise", res, t0)
    draft = {"summary_ar": parsed.summary_ar, "summary_en": parsed.summary_en, "limitations_ar": LIMITATIONS_AR,
             "limitations_en": LIMITATIONS_EN, "overall_risk": level, "extracted_profile": state.get("profile", {}),
             "missing_documents": missing,
             "generation_meta": {"provider": ctx.ai.cfg.provider, "model": ctx.ai.llm.model, "mock": ctx.ai.is_mock,
                                 "embedding_model": ctx.ai.embedder.model, "embedding_mock": ctx.ai.embedder.is_mock,
                                 "injection_flags": state.get("injection_flags", []), "counts": counts,
                                 "evidence_topics": [e["topic"] for e in state.get("evidence", [])]},
             "findings": findings}
    out = await ctx.tools.call(agent, "create_assessment_draft",
                               {"application_id": state["application_id"], "agent_run_id": state["run_id"], "draft": draft})
    ctx.recorder.record(agent, "NODE", "assessment_reporting", duration_ms=int((time.perf_counter() - t0) * 1000), output=out)
    return {"draft_id": out["draft_id"], "draft_version": out["version"]}
