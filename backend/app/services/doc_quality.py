"""Content validation for uploaded documents.

A file only counts as a given document type when its text is readable, substantive and contains the
core elements that type of document is expected to have. Used by the public readiness check.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

MIN_CHARS = 200
MIN_WORDS = 40

# type -> element key -> (label ar, label en, keywords)
ELEMENTS: dict[str, dict[str, tuple[str, str, list[str]]]] = {
    "COMMERCIAL_REGISTRATION": {
        "cr_number": ("رقم سجل تجاري من 10 أرقام", "10-digit CR number", []),  # regex-checked
        "name": ("الاسم التجاري", "Trade name", ["الاسم التجاري", "اسم المنشأة", "اسم الشركة", "trade name", "company name"]),
        "activity": ("النشاط", "Activity", ["النشاط", "activity", "activities"]),
        "dates": ("تاريخ الإصدار أو الانتهاء", "Issue/expiry date", ["تاريخ الإصدار", "تاريخ الانتهاء", "issue date", "expiry date", "تاريخ"]),
        "city": ("المدينة أو العنوان", "City or address", ["المدينة", "العنوان", "city", "address", "الرياض", "جدة", "الدمام", "riyadh", "jeddah"]),
    },
    "BUSINESS_PLAN": {
        "model": ("وصف نموذج العمل والخدمات", "Business model and services", ["نموذج العمل", "business model", "الخدمات", "الخدمة", "المنتج", "product", "service"]),
        "market": ("السوق والعملاء المستهدفون", "Market and target customers", ["السوق", "العملاء المستهدف", "الشريحة المستهدفة", "market", "target customer"]),
        "projections": ("التوقعات المالية", "Financial projections", ["التوقعات المالية", "الإيرادات المتوقعة", "الإيرادات", "projection", "forecast", "revenue"]),
        "capital": ("رأس المال والتمويل", "Capital and funding", ["رأس المال", "capital", "التمويل", "funding"]),
        "staff": ("الموظفون والتوطين", "Staffing and Saudization", ["الموظفين", "التوظيف", "التوطين", "السعودة", "employees", "staff", "headcount", "saudization"]),
        "technology": ("التقنية والمنصة", "Technology and platform", ["التقنية", "المنصة", "التطبيق", "technology", "platform", "infrastructure"]),
    },
    "FINANCIAL_STATEMENTS": {
        "assets": ("الأصول", "Assets", ["الأصول", "الموجودات", "assets"]),
        "liabilities": ("الخصوم", "Liabilities", ["الخصوم", "المطلوبات", "الالتزامات المتداولة", "liabilities"]),
        "equity": ("حقوق الملكية ورأس المال", "Equity and capital", ["حقوق الملكية", "حقوق المساهمين", "رأس المال", "equity"]),
        "income": ("قائمة الدخل", "Income statement", ["قائمة الدخل", "صافي الربح", "صافي الخسارة", "الإيرادات", "income statement", "net profit", "net loss", "revenue"]),
        "auditor": ("رأي المراجع الخارجي", "External auditor's opinion", ["المراجع الخارجي", "مراجع الحسابات", "تقرير المراجع", "مدققة", "auditor", "audited", "audit opinion"]),
        "period": ("الفترة المالية", "Financial period", ["السنة المنتهية", "للسنة المالية", "year ended", "fiscal year", "31 ديسمبر", "31 december"]),
    },
    "AML_CTF_POLICY": {
        "risk_assessment": ("تقييم مخاطر غسل الأموال", "ML/TF risk assessment", ["تقييم المخاطر", "النهج القائم على المخاطر", "risk assessment", "risk-based"]),
        "cdd": ("العناية الواجبة واعرف عميلك", "Customer due diligence / KYC", ["العناية الواجبة", "اعرف عميلك", "التحقق من الهوية", "due diligence", "kyc", "know your customer"]),
        "str": ("الإبلاغ عن العمليات المشتبه بها", "Suspicious transaction reporting", ["الإبلاغ عن العمليات", "العمليات المشتبه", "العمليات المشبوهة", "التحريات المالية", "suspicious transaction", "suspicious activity"]),
        "records": ("حفظ السجلات", "Record keeping", ["حفظ السجلات", "الاحتفاظ بالسجلات", "عشر سنوات", "record keeping", "record retention", "ten years", "10 years"]),
        "officer": ("مسؤول الالتزام أو الإبلاغ", "Compliance / MLRO officer", ["مسؤول الإبلاغ", "مسؤول الالتزام", "mlro", "compliance officer"]),
        "training": ("تدريب الموظفين", "Staff training", ["التدريب", "تدريب الموظفين", "training"]),
        "sanctions": ("فحص قوائم العقوبات", "Sanctions screening", ["العقوبات", "قوائم الحظر", "sanction", "screening"]),
    },
    "CYBERSECURITY_POLICY": {
        "governance": ("حوكمة الأمن السيبراني", "Cybersecurity governance", ["مجلس الإدارة", "لجنة الأمن", "الحوكمة", "board", "governance", "ciso"]),
        "access": ("إدارة الهويات والصلاحيات", "Identity and access management", ["الصلاحيات", "الهويات", "المصادقة", "access control", "identity", "authentication", "mfa"]),
        "encryption": ("التشفير", "Encryption", ["التشفير", "encryption", "encrypted"]),
        "incident": ("الاستجابة للحوادث", "Incident response", ["الحوادث", "الاستجابة", "incident"]),
        "vulnerability": ("إدارة الثغرات واختبار الاختراق", "Vulnerability management / pen testing", ["الثغرات", "اختبار اختراق", "اختبار الاختراق", "vulnerability", "penetration"]),
        "third_party": ("أمن الأطراف الخارجية", "Third-party security", ["الأطراف الخارجية", "الموردين", "مزودي الخدمات", "third part", "vendor", "supplier"]),
        "monitoring": ("المراقبة الأمنية", "Security monitoring", ["المراقبة", "monitoring", "logging", "siem"]),
    },
    "DATA_PROTECTION_POLICY": {
        "lawful_basis": ("أساس المعالجة والموافقة", "Lawful basis and consent", ["أساس المعالجة", "الموافقة", "consent", "lawful basis", "legal basis"]),
        "rights": ("حقوق صاحب البيانات", "Data subject rights", ["حقوق صاحب البيانات", "حق الوصول", "التصحيح", "data subject", "right of access", "rectification"]),
        "retention": ("الاحتفاظ والإتلاف", "Retention and deletion", ["الاحتفاظ", "الإتلاف", "الحذف", "retention", "deletion", "erasure"]),
        "transfer": ("نقل البيانات خارج المملكة", "Cross-border transfer", ["نقل البيانات", "خارج المملكة", "cross-border", "transfer"]),
        "breach": ("الإبلاغ عن تسرب البيانات", "Breach notification", ["تسرب", "اختراق البيانات", "الإبلاغ عن الحوادث", "breach"]),
        "dpo": ("مسؤول حماية البيانات", "Data protection officer", ["مسؤول حماية البيانات", "data protection officer", "dpo"]),
    },
    "GOVERNANCE_STRUCTURE": {
        "board": ("مجلس الإدارة", "Board of directors", ["مجلس الإدارة", "board of directors", "the board"]),
        "committees": ("اللجان", "Committees", ["لجنة", "اللجان", "committee"]),
        "executives": ("الإدارة التنفيذية", "Executive management", ["الرئيس التنفيذي", "الإدارة التنفيذية", "ceo", "executive"]),
        "compliance": ("وظيفة الالتزام", "Compliance function", ["الالتزام", "compliance"]),
        "risk": ("وظيفة المخاطر", "Risk function", ["إدارة المخاطر", "مسؤول المخاطر", "risk management", "chief risk"]),
        "reporting": ("الهيكل التنظيمي وخطوط التقارير", "Org structure and reporting lines", ["الهيكل التنظيمي", "خطوط التقارير", "يرفع تقاريره", "organization", "organisation", "reporting line", "reports to"]),
    },
    "OUTSOURCING_AGREEMENTS": {
        "provider": ("بيانات مزود الخدمة", "Service provider", ["مزود الخدمة", "مزود", "provider", "vendor"]),
        "sla": ("مستوى الخدمة", "Service levels", ["مستوى الخدمة", "service level", "sla"]),
        "audit": ("حق التدقيق", "Right to audit", ["حق التدقيق", "right to audit", "التدقيق", "audit"]),
        "exit": ("خطة الخروج", "Exit plan", ["خطة الخروج", "exit plan", "exit strategy"]),
        "confidentiality": ("السرية وحماية البيانات", "Confidentiality and data protection", ["السرية", "confidential", "حماية البيانات"]),
        "termination": ("الإنهاء", "Termination", ["الإنهاء", "إنهاء", "termination"]),
    },
    "CONSUMER_PROTECTION_POLICY": {
        "complaints": ("آلية الشكاوى", "Complaints handling", ["الشكاوى", "شكوى", "complaint"]),
        "disclosure": ("الإفصاح والشروط", "Disclosure and terms", ["الإفصاح", "الشروط والأحكام", "disclosure", "terms and conditions"]),
        "fair": ("المعاملة العادلة", "Fair treatment", ["المعاملة العادلة", "العدل", "fair treatment", "fairly"]),
        "timelines": ("مدد الاستجابة", "Response timelines", ["أيام عمل", "يوم عمل", "business days", "working days", "خلال"]),
        "fees": ("الرسوم والتكاليف", "Fees and costs", ["الرسوم", "التكلفة", "fees", "charges"]),
        "vulnerable": ("الفئات الأكثر حاجة للحماية", "Vulnerable customers", ["كبار السن", "ذوي الإعاقة", "vulnerable", "الفئات"]),
    },
    "RISK_MANAGEMENT_FRAMEWORK": {
        "appetite": ("الرغبة في المخاطر وحدود التحمل", "Risk appetite and tolerance", ["الرغبة في المخاطر", "تحمل المخاطر", "حدود التحمل", "risk appetite", "tolerance"]),
        "kri": ("مؤشرات المخاطر الرئيسية", "Key risk indicators", ["مؤشرات المخاطر", "key risk indicator", "kri"]),
        "credit": ("مخاطر الائتمان والجدارة", "Credit risk / creditworthiness", ["الائتمان", "الجدارة الائتمانية", "credit"]),
        "operational": ("المخاطر التشغيلية", "Operational risk", ["المخاطر التشغيلية", "operational risk"]),
        "liquidity": ("مخاطر السيولة", "Liquidity risk", ["السيولة", "liquidity"]),
        "reporting": ("التقارير والمراجعة الدورية", "Reporting and periodic review", ["التقارير", "مراجعة دورية", "ربع سنوية", "reporting", "quarterly", "periodic review"]),
    },
}

TYPE_MIN = {t: max(2, math.ceil(len(e) / 2)) for t, e in ELEMENTS.items()}  # elements needed to be "accepted"
_CR = re.compile(r"(?<!\d)[1-7]\d{9}(?!\d)")
_LETTER = re.compile(r"[A-Za-z؀-ۿ]")
_WORD = re.compile(r"[A-Za-z؀-ۿ]{2,}")


@dataclass
class Quality:
    status: str  # ACCEPTED | PARTIAL | REJECTED
    reason_ar: str = ""
    reason_en: str = ""
    found: list[str] = field(default_factory=list)
    missing: list[dict] = field(default_factory=list)


def _norm(text: str) -> str:
    return text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).lower()


def readable(text: str) -> tuple[bool, str, str]:
    """Gate that rejects empty, scanned, garbled or repetitive content."""
    stripped = re.sub(r"\s+", " ", text or "").strip()
    if not stripped:
        return False, "لا يحتوي الملف على نص قابل للقراءة (قد يكون صورة أو مستنداً ممسوحاً ضوئياً). ارفع نسخة نصية.", \
            "No readable text (possibly an image or scanned document). Upload a text-based copy."
    if len(stripped) < MIN_CHARS:
        return False, "محتوى الملف قصير جداً ليكون وثيقة يُعتمد عليها.", "The file content is too short to be a usable document."
    letters = len(_LETTER.findall(stripped))
    if letters / max(1, len(stripped.replace(" ", ""))) < 0.5:
        return False, "محتوى الملف غير مقروء أو مشوّه.", "The file content is unreadable or garbled."
    words = [w.lower() for w in _WORD.findall(stripped)]
    if len(words) < MIN_WORDS:
        return False, "عدد الكلمات في الملف غير كافٍ.", "The file does not contain enough words."
    if len(words) >= 80 and len(set(words)) / len(words) < 0.15:
        return False, "محتوى الملف مكرر وغير حقيقي.", "The file content is repetitive filler."
    return True, "", ""


def assess(doc_type: str, text: str) -> Quality:
    """Score a readable document against the core elements of its type."""
    if doc_type not in ELEMENTS:
        return Quality("REJECTED", "لا يبدو الملف مرتبطاً بوثائق الترخيص المطلوبة.",
                       "The file does not appear to be one of the licensing documents.")
    hay = _norm(text)
    found, missing = [], []
    for key, (ar, en, words) in ELEMENTS[doc_type].items():
        ok = bool(_CR.search(hay)) if key == "cr_number" else any(w.lower() in hay for w in words)
        (found if ok else missing).append(key if ok else {"key": key, "label_ar": ar, "label_en": en})
    if doc_type == "FINANCIAL_STATEMENTS" and len(re.findall(r"\d[\d,\.]{3,}", hay)) < 5:
        missing.append({"key": "figures", "label_ar": "أرقام مالية فعلية", "label_en": "Actual financial figures"})
        return Quality("PARTIAL", "لا يتضمن أرقاماً مالية كافية.", "Does not contain enough financial figures.", found, missing)
    if doc_type == "COMMERCIAL_REGISTRATION" and "cr_number" not in found:
        return Quality("PARTIAL", "لم يُعثر على رقم سجل تجاري صحيح.", "No valid commercial registration number found.", found, missing)
    if len(found) >= TYPE_MIN[doc_type]:
        return Quality("ACCEPTED", found=found, missing=missing)
    if found:
        return Quality("PARTIAL", "الوثيقة لا تغطي العناصر الأساسية المتوقعة.", "The document does not cover the expected core elements.",
                       found, missing)
    return Quality("REJECTED", "محتوى الملف لا يطابق نوع الوثيقة المحدد.", "The content does not match the selected document type.",
                   found, missing)


def cr_numbers(text: str) -> set[str]:
    return set(_CR.findall(_norm(text)))
