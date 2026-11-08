"""Public regulatory readiness check.

Anyone can describe a fintech business and upload its documents. The same deterministic rules used in the
review workspace run against an in-memory application; nothing submitted here is stored. Each requirement
is returned with the passage of the official-source summary it comes from.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from types import SimpleNamespace

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import guard
from app.api.deps import RequestCtx, request_ctx
from app.core.db import get_db
from app.core.errors import AppError, RateLimited
from app.core.ratelimit import limiter
from app.models import DocumentType, Organization, RegulatoryChunk, RegulatoryDocument, ServiceCategory
from app.rag.extract import extract, validate_file
from app.services import doc_quality as dq
from app.services import rules
from app.services.rules import SEVERITY_ORDER

router = APIRouter(tags=["readiness"])

MAX_FILES = 10
MAX_MB = 8
WEIGHT = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}

KEYWORDS: dict[str, list[str]] = {
    "COMMERCIAL_REGISTRATION": ["السجل التجاري", "سجل تجاري", "commercial registration", "عقد التأسيس", "articles of association"],
    "BUSINESS_PLAN": ["خطة العمل", "دراسة الجدوى", "business plan", "feasibility", "نموذج العمل", "business model", "go-to-market"],
    "FINANCIAL_STATEMENTS": ["القوائم المالية", "قوائم مالية", "financial statements", "الميزانية العمومية", "balance sheet", "income statement", "رأس المال المدفوع"],
    "AML_CTF_POLICY": ["غسل الأموال", "تمويل الإرهاب", "money laundering", "aml", "kyc", "اعرف عميلك", "العناية الواجبة"],
    "CYBERSECURITY_POLICY": ["الأمن السيبراني", "أمن المعلومات", "cyber", "information security", "اختبار اختراق", "penetration test", "التشفير", "encryption"],
    "DATA_PROTECTION_POLICY": ["حماية البيانات", "البيانات الشخصية", "data protection", "privacy", "الخصوصية", "pdpl", "الموافقة الصريحة"],
    "GOVERNANCE_STRUCTURE": ["الحوكمة", "مجلس الإدارة", "governance", "board of directors", "الهيكل التنظيمي", "organization chart", "لجنة المراجعة"],
    "OUTSOURCING_AGREEMENTS": ["الإسناد", "outsourcing", "اتفاقية مستوى الخدمة", "service level agreement", "مزود خدمة", "خطة الخروج", "exit plan"],
    "CONSUMER_PROTECTION_POLICY": ["حماية العملاء", "الشكاوى", "consumer protection", "complaints", "الإفصاح", "disclosure", "معاملة العملاء"],
    "RISK_MANAGEMENT_FRAMEWORK": ["إدارة المخاطر", "risk management", "risk appetite", "الجدارة الائتمانية", "creditworthiness", "credit policy", "سياسة الائتمان"],
}

DOC_LABEL_AR = {
    "COMMERCIAL_REGISTRATION": "السجل التجاري وعقد التأسيس", "BUSINESS_PLAN": "خطة العمل ودراسة الجدوى",
    "FINANCIAL_STATEMENTS": "القوائم المالية وإثبات رأس المال", "AML_CTF_POLICY": "سياسة مكافحة غسل الأموال وتمويل الإرهاب",
    "CYBERSECURITY_POLICY": "سياسة الأمن السيبراني", "DATA_PROTECTION_POLICY": "سياسة حماية البيانات الشخصية",
    "GOVERNANCE_STRUCTURE": "هيكل الحوكمة والهيكل التنظيمي", "OUTSOURCING_AGREEMENTS": "اتفاقيات الإسناد وخطة الخروج",
    "CONSUMER_PROTECTION_POLICY": "سياسة حماية العملاء والشكاوى", "RISK_MANAGEMENT_FRAMEWORK": "إطار إدارة المخاطر وسياسة الائتمان",
    "OTHER": "وثيقة أخرى",
}

# Headline rules per activity, each tied to a section of the official-source summaries.
KEY_RULES: dict[str, list[tuple[str, str, str, str]]] = {
    "BNPL": [
        ("الحد الأقصى للتمويل القائم 5,000 ريال للعميل و12 قسطاً كحد أقصى، والتحصيل إلكترونياً.",
         "Max SAR 5,000 outstanding per consumer, up to 12 instalments, electronic collection.", "SAMA-BNPL", "المادة 22"),
        ("لا تُحصَّل رسوم من العميل، ولا يُتعامل مع من هم دون 18 سنة.", "No consumer fees; no customers under 18.", "SAMA-BNPL", "المادة 20"),
        ("نسبة توطين 50% عند البدء ترتفع 5% سنوياً حتى 75%.", "Saudization 50% at launch, +5% yearly up to 75%.", "SAMA-BNPL", "المادة 18"),
        ("ضمان بنكي غير قابل للإلغاء يعادل الحد الأدنى لرأس المال ضمن ملف الترخيص.", "Irrevocable bank guarantee equal to minimum capital in the licence file.", "SAMA-BNPL", "المادة 4"),
    ],
    "DIGITAL_PAYMENTS": [
        ("رأس المال: مليون ريال لمؤسسة المدفوعات الصغرى و3 ملايين للكبرى.", "Capital: SAR 1M micro PI, SAR 3M major PI.", "SAMA-PAYMENTS", "القسم 2"),
        ("رأس المال المستمر للكبرى: الأعلى من الأولي أو 1% من متوسط القيمة الشهرية للعمليات.", "Ongoing capital (major PI): higher of initial or 1% of monthly volume.", "SAMA-PAYMENTS", "القسم 3"),
        ("حماية أموال العملاء وفصلها.", "Safeguard and segregate customer funds.", "SAMA-PAYMENTS", "القسم 7"),
    ],
    "DIGITAL_WALLET": [
        ("رأس المال: مليونا ريال للنقود الإلكترونية الصغرى و10 ملايين للكبرى.", "Capital: SAR 2M micro EMI, SAR 10M major EMI.", "SAMA-PAYMENTS", "القسم 2"),
        ("حد شهري 20,000 ريال لكل عميل في الترخيص الصغير.", "SAR 20,000 monthly limit per customer under the micro licence.", "SAMA-PAYMENTS", "القسم 4"),
        ("رأس المال المستمر للكبرى: الأعلى من الأولي أو 2% من متوسط النقود الإلكترونية القائمة.", "Ongoing capital (major EMI): higher of initial or 2% of average e-money.", "SAMA-PAYMENTS", "القسم 3"),
    ],
    "OPEN_BANKING": [
        ("موافقة صريحة من المستخدم قبل تقديم الخدمة.", "Explicit user consent before providing the service.", "SAMA-OPENBANKING", "الفصل 2"),
        ("حذف بيانات المستخدم عند سحب الموافقة.", "Delete user data when consent is withdrawn.", "SAMA-OPENBANKING", "الفصل 3"),
        ("تأمين المسؤولية المهنية أو ضمان مماثل.", "Professional indemnity insurance or equivalent guarantee.", "SAMA-OPENBANKING", "الفصل 4"),
    ],
    "LENDING": [
        ("رأس المال 10 ملايين ريال لشركة التمويل المصغر بالتقنية المالية (20 مليوناً لغيرها).", "Capital SAR 10M for fintech microfinance (20M otherwise).", "SAMA-MICROFINANCE", "المادة 4"),
        ("حد التمويل 25,000 ريال للمقترض عبر التقنية المالية.", "SAR 25,000 cap per borrower for fintech microfinance.", "SAMA-MICROFINANCE", "المادة 50"),
        ("التمويل الجماعي بالدين: رأس مال 5 ملايين ريال.", "Debt crowdfunding: SAR 5M capital.", "SAMA-MICROFINANCE", "القسم 2"),
    ],
}


def classify(filename: str, text: str) -> tuple[str, list[str]]:
    """Primary document type plus other types the same file substantially covers."""
    hay = text[:30000].lower()
    name = filename.lower().replace("_", " ").replace("-", " ")
    scores = {}
    for t, words in KEYWORDS.items():
        s = sum(hay.count(w.lower()) for w in words) + sum(3 for w in words if w.lower() in name)
        if s:
            scores[t] = s
    if not scores or max(scores.values()) < 2:
        return "OTHER", []
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    primary = ranked[0][0]
    also = [t for t, s in ranked[1:] if s >= 3]
    return primary, also


def _main_org(db: Session) -> Organization:
    org = db.scalar(select(Organization).where(Organization.slug == "rip-main"))
    if org is None:
        org = db.scalar(select(Organization).order_by(Organization.created_at).limit(1))
    if org is None:
        raise AppError("Regulatory catalogue not loaded yet", "لم يتم تحميل الكتالوج التنظيمي بعد", status_code=503, code="NOT_READY")
    return org


def _evidence(db: Session, org_id, code: str, section: str) -> dict | None:
    prefix = section.split(" - ")[0].strip()
    rows = db.execute(select(RegulatoryChunk, RegulatoryDocument).join(RegulatoryDocument, RegulatoryDocument.id == RegulatoryChunk.document_id)
                      .where(RegulatoryDocument.org_id == org_id, RegulatoryDocument.document_code == code,
                             RegulatoryDocument.deleted_at.is_(None), RegulatoryDocument.classification == "public")
                      .order_by(RegulatoryChunk.chunk_index)).all()
    for ch, doc in rows:
        if doc.current_version_id and ch.version_id != doc.current_version_id:
            continue
        if ch.section.startswith(prefix + " ") or ch.section == prefix or ch.section.startswith(prefix + "-"):
            body = ch.text.split("\n", 1)[1].strip() if "\n" in ch.text and ch.text.startswith(ch.section) else ch.text
            return {"document_code": code, "title_ar": doc.title_ar, "title_en": doc.title_en, "section": ch.section,
                    "text": body[:900], "source_url": doc.source}
    return None


def _money(v: float) -> str:
    return f"{v:,.0f}"


def _action(r: dict) -> str:
    parts = []
    inc = r.get("incomplete") or {}
    for t, miss in inc.items():
        parts.append(f"استكمل {DOC_LABEL_AR.get(t, t)} بإضافة: " + "، ".join(m["label_ar"] for m in miss))
    if r["missing_documents"] and not inc:
        parts.append("قدّم: " + "، ".join(DOC_LABEL_AR.get(t, t) for t in r["missing_documents"]))
    d = r.get("detail") or ""
    m = re.search(r"paid_up_capital_sar=([0-9.]+|None) >= ([0-9.]+)", d)
    if m:
        need = float(m.group(2))
        parts.append(f"رأس المال المدفوع يجب ألا يقل عن {_money(need)} ريال")
    elif "paid_up_capital_sar not provided" in d:
        parts.append("أدخل رأس المال المدفوع أو أرفق ما يثبته")
    return "؛ ".join(parts)


@router.post("/readiness/check")
async def readiness_check(
    company_name: str = Form("", max_length=200),
    service_category: ServiceCategory = Form(...),
    description: str = Form("", max_length=6000),
    paid_up_capital_sar: float | None = Form(None, ge=0, le=1e12),
    expected_monthly_volume_sar: float | None = Form(None, ge=0, le=1e13),
    data_hosting_location: str = Form("", max_length=120),
    uses_third_party_providers: bool = Form(False),
    document_types: str = Form("", max_length=2000),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    rc: RequestCtx = Depends(request_ctx),
):
    if not limiter.hit(f"readiness:{rc.ip or 'local'}", 12, 60):
        raise RateLimited()
    if len(files) > MAX_FILES:
        raise AppError(f"At most {MAX_FILES} files", f"الحد الأقصى {MAX_FILES} ملفات", status_code=400, code="TOO_MANY_FILES")
    overrides = [s.strip() for s in document_types.split(",")] if document_types else []
    org = _main_org(db)

    docs, analysed = [], []
    partial: dict[str, list[dict]] = {}  # type -> missing elements, for documents that exist but are incomplete
    texts = [description] if description.strip() else []
    seen_hashes: set[str] = set()
    for i, f in enumerate(files):
        name = f.filename or "file"
        data = await f.read()
        entry = {"filename": name, "size_bytes": len(data), "pages": 0, "detected_type": "OTHER", "assigned_types": [],
                 "status": "REJECTED", "reason_ar": "", "reason_en": "", "elements_found": [], "elements_missing": [],
                 "suspicious_instructions": False}
        analysed.append(entry)
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen_hashes:
            entry.update(reason_ar="ملف مكرر — رُفع الملف نفسه أكثر من مرة.", reason_en="Duplicate file — the same file was uploaded twice.")
            continue
        seen_hashes.add(digest)
        try:
            validate_file(name, data, MAX_MB)
            ex = extract(name, data)
        except AppError as err:
            entry.update(reason_ar=err.message_ar, reason_en=err.message)
            continue
        except Exception:  # corrupt, encrypted or malformed files
            entry.update(reason_ar="تعذرت قراءة الملف؛ قد يكون تالفاً أو محمياً بكلمة مرور.",
                         reason_en="The file could not be read; it may be corrupt or password-protected.")
            continue
        text = "\n".join(p.text for p in ex.pages)
        entry["pages"] = len(ex.pages)
        ok, rar, ren = dq.readable(text)
        if not ok:
            entry.update(reason_ar=rar, reason_en=ren)
            continue
        flagged = guard.scan(text)
        entry["suspicious_instructions"] = flagged.flagged
        primary, also = classify(name, text)
        chosen = overrides[i] if i < len(overrides) and overrides[i] in DocumentType.__members__ and overrides[i] != "OTHER" else None
        entry["detected_type"] = primary
        candidates = [chosen] if chosen else [primary, *also]
        accepted, best = [], None
        for typ in dict.fromkeys(candidates):
            q = dq.assess(typ, text)
            if q.status == "ACCEPTED":
                accepted.append(typ)
                best = best or q
            elif q.status == "PARTIAL" and (typ == candidates[0]):
                best = best or q
                partial.setdefault(typ, q.missing)
            elif best is None and typ == candidates[0]:
                best = q
        if accepted:
            entry.update(status="ACCEPTED", assigned_types=accepted, elements_found=best.found, elements_missing=best.missing)
        elif best and best.status == "PARTIAL":
            entry.update(status="PARTIAL", assigned_types=[candidates[0]], reason_ar=best.reason_ar, reason_en=best.reason_en,
                         elements_found=best.found, elements_missing=best.missing)
        else:
            entry.update(reason_ar=best.reason_ar if best else "لا يبدو الملف مرتبطاً بوثائق الترخيص المطلوبة.",
                         reason_en=best.reason_en if best else "The file does not appear to be a licensing document.")
            continue
        for typ in accepted:
            docs.append(SimpleNamespace(id=uuid.uuid4(), document_type=DocumentType(typ), processing_status="PROCESSED",
                                        extracted_text=text, filename=name))
            partial.pop(typ, None)
        texts.append(text)
    for typ in {d.document_type.value for d in docs}:
        partial.pop(typ, None)

    profile = rules.extract_profile(texts)
    capital = paid_up_capital_sar if paid_up_capital_sar is not None else profile.get("paid_up_capital_sar")
    app = SimpleNamespace(org_id=org.id, service_category=service_category, paid_up_capital_sar=capital,
                          expected_monthly_volume_sar=expected_monthly_volume_sar,
                          data_hosting_location=data_hosting_location.strip() or profile.get("data_hosting_mention", ""),
                          uses_third_party_providers=uses_third_party_providers, extracted_profile=profile, documents=docs)

    reqs = rules.evaluate_requirements(db, app)
    for r in reqs:  # required document exists but is incomplete -> needs information rather than absent
        incomplete = [m for m in r["missing_documents"] if m in partial]
        if incomplete and len(incomplete) == len(r["missing_documents"]) and "not satisfied" not in (r["detail"] or ""):
            r["outcome"] = "INSUFFICIENT_INFORMATION"
            r["incomplete"] = {m: partial[m] for m in incomplete}

    consistency = []
    cap_doc = profile.get("paid_up_capital_sar")
    if paid_up_capital_sar and cap_doc and abs(cap_doc - paid_up_capital_sar) > 0.05 * paid_up_capital_sar:
        consistency.append({"ar": f"رأس المال المُدخل ({_money(paid_up_capital_sar)} ريال) لا يطابق المذكور في الوثائق ({_money(cap_doc)} ريال).",
                            "en": f"Entered capital (SAR {_money(paid_up_capital_sar)}) differs from the documents (SAR {_money(cap_doc)})."})
    crs = set().union(*(dq.cr_numbers(d.extracted_text) for d in docs)) if docs else set()
    if len(crs) > 1:
        consistency.append({"ar": "وردت أرقام سجل تجاري مختلفة في الوثائق: " + "، ".join(sorted(crs)),
                            "en": "Different CR numbers appear across documents: " + ", ".join(sorted(crs))})
    cname = company_name.strip()
    if cname and docs and len(cname) >= 4:
        core = re.sub(r"^(شركة|مؤسسة)\s+", "", cname).split()[0].lower()
        if not any(core in (d.extracted_text or "").lower() for d in docs):
            consistency.append({"ar": "لم يرد اسم الشركة في أي من الوثائق المقبولة؛ تأكد أن الوثائق تخص شركتك.",
                                "en": "The company name does not appear in any accepted document; check the documents belong to your company."})
    risks = [r for r in rules.risk_indicators(db, app) if r["code"] != "SEC-INJ-01"]
    doc_check = rules.check_required_documents(db, app)

    total = sum(WEIGHT.get(r["severity"], 1) for r in reqs) or 1
    def credit(r):  # noqa: E306
        if r["outcome"] == "MET":
            return 1.0
        if r["outcome"] == "INSUFFICIENT_INFORMATION":
            return 0.3
        rule_ok = "not satisfied" not in (r["detail"] or "") and "not provided" not in (r["detail"] or "")
        return 0.4 if rule_ok and r["missing_documents"] else 0.0  # threshold met, evidence document still missing

    got = sum(WEIGHT.get(r["severity"], 1) * credit(r) for r in reqs)
    score = round(100 * got / total)
    penalty = sum(5 if r["severity"] in ("HIGH", "CRITICAL") else 2 for r in risks)
    score = max(0, score - penalty)
    level = "HIGH" if score >= 80 else "MEDIUM" if score >= 50 else "LOW"

    cache: dict[tuple, dict | None] = {}

    def ev(code, section):
        k = (code, section)
        if k not in cache:
            cache[k] = _evidence(db, org.id, code, section)
        return cache[k]

    items = []
    for r in sorted(reqs, key=lambda r: (r["outcome"] == "MET", -SEVERITY_ORDER.get(r["severity"], 0))):
        items.append({"code": r["code"], "title_ar": r["title_ar"], "title_en": r["title_en"], "severity": r["severity"],
                      "outcome": r["outcome"], "missing_documents": r["missing_documents"], "action_ar": _action(r) if r["outcome"] != "MET" else "",
                      "incomplete": r.get("incomplete", {}),
                      "evidence": ev(r["source_document_code"], r["source_section"])})
    risk_items = []
    for r in risks:
        risk_items.append({"code": r["code"], "severity": r["severity"], "title_ar": r["title_ar"], "title_en": r["title_en"],
                           "observed_value": r["observed_value"]})
    key_rules = [{"text_ar": ar, "text_en": en, "evidence": ev(code, sec)} for ar, en, code, sec in KEY_RULES.get(service_category.value, [])]

    steps = [i["action_ar"] for i in items if i["action_ar"]]
    rejected = [a["filename"] for a in analysed if a["status"] == "REJECTED"]
    if rejected:
        steps.insert(0, "أعد رفع الملفات المرفوضة بنسخ نصية كاملة: " + "، ".join(rejected))
    if any(r["code"] == "RISK-HOST-01" for r in risks):
        steps.append("وثّق أساس نقل البيانات خارج المملكة وتقييم المخاطر وفق لائحة نقل البيانات، أو انقل الاستضافة إلى داخل المملكة")
    if any(r["code"] == "RISK-CO-01" for r in risks):
        steps.append("عيّن مسؤول التزام ومسؤول إبلاغ عن غسل الأموال قبل تقديم الطلب")
    steps.append("راجع النص الرسمي لكل متطلب عبر الروابط المرفقة قبل التقديم إلى الجهة المختصة")

    return {
        "company_name": company_name.strip(), "service_category": service_category.value,
        "score": score, "level": level,
        "counts": {"met": sum(r["outcome"] == "MET" for r in reqs), "gaps": sum(r["outcome"] == "POTENTIAL_GAP" for r in reqs),
                   "insufficient": sum(r["outcome"] == "INSUFFICIENT_INFORMATION" for r in reqs), "risks": len(risk_items)},
        "requirements": items, "risks": risk_items, "key_rules": key_rules,
        "consistency": consistency,
        "documents": {"analysed": analysed, "required": doc_check["required"], "present": doc_check["present"],
                      "missing": [m["document_type"] for m in doc_check["missing"]]},
        "profile": {k: v for k, v in profile.items() if k in ("paid_up_capital_sar", "has_compliance_officer", "has_mlro",
                                                               "data_hosting_mention", "employees", "projected_growth_pct")},
        "capital_used": capital, "next_steps": list(dict.fromkeys(steps)),
        "stored": False,
        "notice_ar": "تقييم أولي لدعم القرار وليس استشارة قانونية أو قراراً رسمياً. لا تُحفظ الملفات المرفوعة.",
        "notice_en": "Preliminary decision support — not legal advice or an official decision. Uploaded files are not stored.",
    }
