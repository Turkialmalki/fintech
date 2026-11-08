"""Deterministic business rules: required documents, configured requirement checks, risk indicators.

These rules are configuration (regulatory_requirements + system_settings) and run without any
model. Agents may add contextual observations, but mandatory checks always come from here.
"""
from __future__ import annotations

import operator
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import guard
from app.models import FintechApplication, RegulatoryRequirement, SystemSetting

OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq, "!=": operator.ne}

DEFAULT_RISK_RULES: list[dict] = [
    {"code": "RISK-HOST-01", "severity": "HIGH", "field": "data_hosting_location", "op": "not_in", "value": ["KSA", "Saudi Arabia", "السعودية", "الرياض", "جدة", "الدمام"],
     "title_ar": "استضافة بيانات العملاء خارج المملكة", "title_en": "Customer data hosted outside the Kingdom",
     "evidence_query": "استضافة بيانات العملاء داخل المملكة"},
    {"code": "RISK-TPP-01", "severity": "MEDIUM", "field": "uses_third_party_providers", "op": "==", "value": True,
     "title_ar": "الاعتماد على مزودي خدمات خارجيين في وظائف جوهرية", "title_en": "Reliance on third-party providers for core functions",
     "evidence_query": "الإسناد إلى أطراف خارجية خطة الخروج"},
    {"code": "RISK-VOL-01", "severity": "MEDIUM", "field": "expected_monthly_volume_sar", "op": ">", "value": 50_000_000,
     "title_ar": "حجم عمليات شهري متوقع مرتفع", "title_en": "High expected monthly transaction volume",
     "evidence_query": "مراقبة العمليات مكافحة غسل الأموال"},
    {"code": "RISK-GROW-01", "severity": "MEDIUM", "profile_field": "projected_growth_pct", "op": ">", "value": 300,
     "title_ar": "نمو متوقع يتجاوز 300% في السنة الأولى", "title_en": "Projected first-year growth above 300%",
     "evidence_query": "rapid projected growth exceeding 300 percent"},
    {"code": "RISK-CO-01", "severity": "HIGH", "profile_field": "has_compliance_officer", "op": "==", "value": False,
     "title_ar": "عدم وجود مسؤول التزام مستقل", "title_en": "No independent compliance officer identified",
     "evidence_query": "مسؤول للالتزام يتمتع بالاستقلالية"},
]

SEVERITY_ORDER = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def get_setting(db: Session, org_id, key: str, default: Any) -> Any:
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key, SystemSetting.org_id == org_id))
    if row is None:
        row = db.scalar(select(SystemSetting).where(SystemSetting.key == key, SystemSetting.org_id.is_(None)))
    return row.value.get("value", default) if row else default


def requirements_for(db: Session, app: FintechApplication) -> list[RegulatoryRequirement]:
    rows = db.scalars(select(RegulatoryRequirement).where(
        RegulatoryRequirement.org_id == app.org_id, RegulatoryRequirement.active.is_(True),
        RegulatoryRequirement.deleted_at.is_(None)).order_by(RegulatoryRequirement.code)).all()
    cat = app.service_category.value
    return [r for r in rows if not r.service_categories or cat in r.service_categories]


def check_required_documents(db: Session, app: FintechApplication) -> dict:
    present = {d.document_type.value for d in app.documents if d.processing_status == "PROCESSED"}
    failed = {d.document_type.value for d in app.documents if d.processing_status == "FAILED"}
    required: dict[str, list[str]] = {}
    for r in requirements_for(db, app):
        for t in r.required_document_types:
            required.setdefault(t, []).append(r.code)
    missing = [{"document_type": t, "requirement_codes": codes, "failed_processing": t in failed}
               for t, codes in sorted(required.items()) if t not in present]
    return {"required": sorted(required), "present": sorted(present), "missing": missing,
            "complete": not missing, "rule_source": "regulatory_requirements (configured, synthetic)"}


def _cmp(actual: Any, op: str, expected: Any) -> bool | None:
    if actual is None:
        return None
    if op == "in":
        return actual in expected
    if op == "not_in":
        return not any(str(e).lower() in str(actual).lower() for e in expected)
    try:
        return OPS[op](float(actual) if isinstance(expected, (int, float)) and not isinstance(expected, bool) else actual, expected)
    except (TypeError, ValueError, KeyError):
        return None


def evaluate_requirements(db: Session, app: FintechApplication) -> list[dict]:
    """Evaluate structured rules attached to configured requirements."""
    docs = check_required_documents(db, app)
    missing_types = {m["document_type"] for m in docs["missing"]}
    results = []
    for r in requirements_for(db, app):
        outcome, detail = "MET", ""
        if r.rule:
            fld = r.rule.get("field")
            actual = getattr(app, fld, None) if fld else None
            ok = _cmp(actual, r.rule.get("op", ">="), r.rule.get("value"))
            if ok is None:
                outcome, detail = "INSUFFICIENT_INFORMATION", f"{fld} not provided"
            elif not ok:
                outcome, detail = "POTENTIAL_GAP", f"{fld}={actual} {r.rule.get('op')} {r.rule.get('value')} not satisfied"
        miss = [t for t in r.required_document_types if t in missing_types]
        if miss:
            outcome = "POTENTIAL_GAP" if outcome == "MET" else outcome
            detail = (detail + "; " if detail else "") + "missing documents: " + ", ".join(miss)
        results.append({"code": r.code, "title_ar": r.title_ar, "title_en": r.title_en, "severity": r.severity,
                        "outcome": outcome, "detail": detail, "missing_documents": miss,
                        "source_document_code": r.source_document_code, "source_section": r.source_section,
                        "is_synthetic": r.is_synthetic})
    return results


def risk_indicators(db: Session, app: FintechApplication) -> list[dict]:
    rules = get_setting(db, app.org_id, "risk.rules", DEFAULT_RISK_RULES)
    profile = app.extracted_profile or {}
    out = []
    for rule in rules:
        if "profile_field" in rule:
            actual = profile.get(rule["profile_field"])
        else:
            actual = getattr(app, rule["field"], None)
            if isinstance(actual, str) and not actual.strip():
                actual = None
        hit = _cmp(actual, rule["op"], rule["value"])
        if hit:
            out.append({"code": rule["code"], "severity": rule["severity"], "title_ar": rule["title_ar"],
                        "title_en": rule["title_en"], "observed_value": actual, "rule": f"{rule.get('field') or rule.get('profile_field')} {rule['op']} {rule['value']}",
                        "evidence_query": rule.get("evidence_query", ""), "origin": "RULE"})
    # indirect prompt-injection inside submitted documents is itself a risk indicator
    for d in app.documents:
        s = guard.scan(d.extracted_text or "")
        if s.flagged:
            out.append({"code": "SEC-INJ-01", "severity": "HIGH",
                        "title_ar": f"تعليمات مضمّنة مشبوهة في الوثيقة المرفوعة ({d.filename})",
                        "title_en": f"Suspicious embedded instructions in uploaded document ({d.filename})",
                        "observed_value": s.matches[:3], "rule": "prompt-injection pattern scan",
                        "document_id": str(d.id), "origin": "RULE"})
    return out


def overall_risk(levels: list[str]) -> str:
    if not levels:
        return "LOW"
    top = max(levels, key=lambda s: SEVERITY_ORDER.get(s, 0))
    return top if top != "INFO" else "LOW"


_NUM = r"([0-9][0-9,\.]*)"


def extract_profile(texts: list[str]) -> dict:
    """Deterministic extraction from application documents (regex; Arabic + English)."""
    blob = "\n".join(texts)
    norm = blob.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    prof: dict[str, Any] = {}
    m = re.search(r"(السجل التجاري|Commercial Registration|CR)\s*(رقم|No\.?|Number)?\s*[:：]?\s*(\d{10})", norm, re.I)
    if m:
        prof["commercial_registration"] = m.group(3)
    m = re.search(r"(رأس المال المدفوع|paid[- ]up capital)[^0-9]{0,40}" + _NUM, norm, re.I)
    if m:
        try:
            prof["paid_up_capital_sar"] = float(m.group(2).replace(",", ""))
        except ValueError:
            pass
    m = re.search(r"(نمو|growth)[^0-9%]{0,40}" + _NUM + r"\s*(%|٪|percent|بالمئة)", norm, re.I)
    if m:
        try:
            prof["projected_growth_pct"] = float(m.group(2).replace(",", ""))
        except ValueError:
            pass
    if re.search(r"(مسؤول (ال)?التزام|compliance officer)", norm, re.I):
        prof["has_compliance_officer"] = not re.search(r"(لا يوجد|لم يتم تعيين|no|not yet appointed)[^.\n]{0,30}(مسؤول (ال)?التزام|compliance officer)", norm, re.I)
    if re.search(r"(مسؤول (ال)?إبلاغ|MLRO|money laundering reporting officer)", norm, re.I):
        prof["has_mlro"] = True
    m = re.search(r"(استضافة|hosted|hosting)[^.\n]{0,60}(فرانكفورت|Frankfurt|Ireland|أيرلندا|Dublin|Singapore|سنغافورة|الرياض|Riyadh|جدة|Jeddah|KSA|السعودية)", norm, re.I)
    if m:
        prof["data_hosting_mention"] = m.group(2)
    m = re.search(r"(عدد الموظفين|employees)[^0-9]{0,20}" + _NUM, norm, re.I)
    if m:
        try:
            prof["employees"] = int(float(m.group(2).replace(",", "")))
        except ValueError:
            pass
    return prof
