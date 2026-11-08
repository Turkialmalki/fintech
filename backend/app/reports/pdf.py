"""Arabic (RTL) and English (LTR) assessment report PDFs.

Arabic shaping: arabic_reshaper + python-bidi. Lines are wrapped in *logical* order first and
each line is then reordered visually; this avoids the reversed-line-order bug of wrapping
already-reordered text. Embedded font: IBM Plex Sans Arabic (SIL OFL 1.1, see fonts/OFL.txt).
The report is explicitly NOT an approval certificate.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_DIR = Path(__file__).parent / "fonts"
_registered = False

NAVY = colors.HexColor("#142238")
MUTED = colors.HexColor("#68778B")
BORDER = colors.HexColor("#E5EAF0")
SURFACE2 = colors.HexColor("#F1F4F8")
PRIMARY = colors.HexColor("#2457D6")
SEV = {"CRITICAL": "#B4232A", "HIGH": "#D94B52", "MEDIUM": "#D99024", "LOW": "#15966A", "INFO": "#6479E8", "UNDETERMINED": "#68778B"}


def _fonts() -> None:
    global _registered
    if _registered:
        return
    pdfmetrics.registerFont(TTFont("Plex", str(FONT_DIR / "IBMPlexSansArabic-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Plex-SemiBold", str(FONT_DIR / "IBMPlexSansArabic-SemiBold.ttf")))
    pdfmetrics.registerFont(TTFont("Plex-Bold", str(FONT_DIR / "IBMPlexSansArabic-Bold.ttf")))
    _registered = True


_reshaper = arabic_reshaper.ArabicReshaper(configuration={"delete_harakat": False, "support_ligatures": True})


def shape_line(text: str, rtl: bool) -> str:
    if not rtl:
        return text
    return get_display(_reshaper.reshape(text), base_dir="R")


def wrap_logical(text: str, font: str, size: float, width: float, rtl: bool) -> list[str]:
    out: list[str] = []
    for para in (text or "").split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            cand = (cur + " " + w).strip()
            measured = _reshaper.reshape(cand) if rtl else cand
            if pdfmetrics.stringWidth(measured, font, size) <= width or not cur:
                cur = cand
            else:
                out.append(cur)
                cur = w
        out.append(cur)
    return out


class Builder:
    def __init__(self, lang: str):
        _fonts()
        self.rtl = lang == "ar"
        self.lang = lang
        al = TA_RIGHT if self.rtl else TA_LEFT
        self.styles = {
            "title": ParagraphStyle("t", fontName="Plex-Bold", fontSize=17, leading=24, textColor=NAVY, alignment=al),
            "h2": ParagraphStyle("h2", fontName="Plex-SemiBold", fontSize=12, leading=18, textColor=NAVY, alignment=al, spaceBefore=8, spaceAfter=4),
            "body": ParagraphStyle("b", fontName="Plex", fontSize=9.5, leading=15, textColor=NAVY, alignment=al),
            "muted": ParagraphStyle("m", fontName="Plex", fontSize=8, leading=12, textColor=MUTED, alignment=al),
            "cell": ParagraphStyle("c", fontName="Plex", fontSize=8.5, leading=12.5, textColor=NAVY, alignment=al),
            "cellb": ParagraphStyle("cb", fontName="Plex-SemiBold", fontSize=8.5, leading=12.5, textColor=NAVY, alignment=al),
        }

    def p(self, text: str, style: str = "body", width: float = 170 * mm, color: str | None = None) -> Paragraph:
        st = self.styles[style]
        lines = wrap_logical(str(text), st.fontName, st.fontSize, width - 10, self.rtl)
        html = "<br/>".join(escape(shape_line(ln, self.rtl)) for ln in lines)
        if color:
            html = f'<font color="{color}">{html}</font>'
        return Paragraph(html, st)

    def table(self, rows: list[list], widths: list[float], header: bool = True) -> Table:
        if self.rtl:  # RTL tables: first logical column on the right
            rows = [list(reversed(r)) for r in rows]
            widths = list(reversed(widths))
        cells = [[c if not isinstance(c, str) else self.p(c, "cellb" if header and i == 0 else "cell", widths[j] - 12) for j, c in enumerate(r)]
                 for i, r in enumerate(rows)]
        t = Table(cells, colWidths=widths, repeatRows=1 if header else 0)
        style = [("GRID", (0, 0), (-1, -1), 0.5, BORDER), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                 ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
        if header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), SURFACE2))
        t.setStyle(TableStyle(style))
        return t


L = {
    "ar": {"title": "تقرير التقييم الأولي", "product": "منظومة الرصد التنظيمي الذكي",
           "disclaimer": "تقرير أولي لدعم المحلل — ليس قراراً تنظيمياً أو قرار ترخيص ولا يمثل موافقة. تستند المتطلبات إلى الأنظمة المنشورة، والنص الرسمي هو المرجع.",
           "app": "بيانات الطلب", "ref": "المرجع", "company": "الشركة", "category": "فئة الخدمة", "status": "حالة سير العمل",
           "cr": "السجل التجاري", "capital": "رأس المال المدفوع (ريال)", "hosting": "موقع الاستضافة",
           "summary": "الملخص", "risk": "مستوى المخاطر الأولي", "findings": "النتائج", "sev": "الأهمية", "cat": "النوع",
           "finding": "النتيجة", "evidence": "الدليل", "interp": "التفسير", "source": "المصدر", "missing": "الوثائق الناقصة",
           "none": "لا يوجد", "comments": "ملاحظات المراجعة", "reviewer": "المراجع", "decision": "القرار", "date": "التاريخ",
           "limitations": "القيود", "meta": "بيانات الإصدار والتدقيق", "version": "إصدار المسودة", "draft_status": "حالة المسودة",
           "authored": "المصدر", "generated": "تاريخ الإنشاء", "generated_by": "أنشئ بواسطة", "model": "النموذج", "run": "معرّف التشغيل",
           "draft_id": "معرّف المسودة", "page": "صفحة", "verified": "استشهاد متحقق منه", "unverified": "استشهاد غير متحقق",
           "ai": "مُولّد آلياً", "human": "من المحلل", "mixed": "آلي مع تعديل بشري", "notes": "ملاحظات المحلل", "mock": "تحليل قائم على القواعد"},
    "en": {"title": "Preliminary Assessment Report", "product": "Saudi Fintech Regulatory Intelligence Platform",
           "disclaimer": "Preliminary analyst-support report — not a regulatory or licensing decision and not an approval. Requirements cite published regulations; the official text prevails.",
           "app": "Application", "ref": "Reference", "company": "Company", "category": "Service category", "status": "Workflow status",
           "cr": "Commercial registration", "capital": "Paid-up capital (SAR)", "hosting": "Hosting location",
           "summary": "Summary", "risk": "Preliminary risk level", "findings": "Findings", "sev": "Severity", "cat": "Type",
           "finding": "Finding", "evidence": "Evidence", "interp": "Interpretation", "source": "Source", "missing": "Missing documents",
           "none": "None", "comments": "Review comments", "reviewer": "Reviewer", "decision": "Decision", "date": "Date",
           "limitations": "Limitations", "meta": "Version and audit metadata", "version": "Draft version", "draft_status": "Draft status",
           "authored": "Authored by", "generated": "Generated at", "generated_by": "Generated by", "model": "Model", "run": "Run ID",
           "draft_id": "Draft ID", "page": "p.", "verified": "verified citation", "unverified": "unverified citation",
           "ai": "AI-generated", "human": "Analyst", "mixed": "AI with human edits", "notes": "Analyst notes", "mock": "rule-based analysis"},
}


AR_LABELS = {
    "BNPL": "الشراء الآن والدفع لاحقاً", "DIGITAL_PAYMENTS": "المدفوعات الرقمية", "OPEN_BANKING": "المصرفية المفتوحة",
    "LENDING": "التمويل الرقمي", "DIGITAL_WALLET": "المحافظ الرقمية",
    "DRAFT": "مسودة", "SUBMITTED": "مقدّم", "DOCUMENT_PROCESSING": "معالجة الوثائق", "AI_ANALYSIS": "تحليل ذكي",
    "PENDING_HUMAN_REVIEW": "بانتظار المراجعة البشرية", "ADDITIONAL_INFORMATION_REQUIRED": "يتطلب استكمال بيانات",
    "APPROVED_FOR_NEXT_REVIEW_STAGE": "محال للمرحلة التالية", "CLOSED": "مغلق",
    "CRITICAL": "حرجة", "HIGH": "عالية", "MEDIUM": "متوسطة", "LOW": "منخفضة", "INFO": "للعلم", "UNDETERMINED": "غير محدد",
    "REGULATORY": "متطلب قد ينطبق", "RISK": "مؤشر مخاطر", "GAP": "فجوة محتملة", "MISSING_INFORMATION": "معلومات ناقصة",
    "OBSERVATION": "ملاحظة", "PENDING_REVIEW": "بانتظار المراجعة", "RETURNED": "معادة", "APPROVED_FOR_NEXT_STAGE": "محالة للمرحلة التالية",
    "REJECTED": "مرفوضة", "SUPERSEDED": "إصدار سابق", "APPROVE_FOR_NEXT_STAGE": "إحالة للمرحلة التالية", "RETURN": "إعادة",
    "REJECT": "رفض", "REQUEST_INFORMATION": "طلب استكمال بيانات", "COMMENT": "ملاحظة",
    "COMMERCIAL_REGISTRATION": "السجل التجاري", "BUSINESS_PLAN": "خطة العمل", "FINANCIAL_STATEMENTS": "القوائم المالية المدققة",
    "AML_CTF_POLICY": "سياسة مكافحة غسل الأموال", "CYBERSECURITY_POLICY": "سياسة الأمن السيبراني",
    "DATA_PROTECTION_POLICY": "سياسة حماية البيانات", "GOVERNANCE_STRUCTURE": "هيكل الحوكمة", "OUTSOURCING_AGREEMENTS": "اتفاقيات الإسناد",
    "CONSUMER_PROTECTION_POLICY": "سياسة حماية العملاء", "RISK_MANAGEMENT_FRAMEWORK": "إطار إدارة المخاطر",
}


def build_report(*, lang: str, app: dict, draft: dict, reviews: list[dict], generated_by: str) -> bytes:
    b = Builder(lang)
    t = L[lang]

    def lb(code: str) -> str:
        return AR_LABELS.get(code, code) if b.rtl else code.replace("_", " ").title() if code and code.isupper() else code
    buf = io.BytesIO()
    W = 170 * mm

    def on_page(c, doc):
        c.saveState()
        c.setFillColor(PRIMARY)
        c.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, fill=1, stroke=0)
        c.setFont("Plex", 7.5)
        c.setFillColor(MUTED)
        footer = shape_line(f"{t['product']} — {t['disclaimer'][:70]}…", b.rtl)
        page = shape_line(f"{t['page']} {doc.page}", b.rtl)
        if b.rtl:
            c.drawRightString(A4[0] - 20 * mm, 10 * mm, footer)
            c.drawString(20 * mm, 10 * mm, page)
        else:
            c.drawString(20 * mm, 10 * mm, footer)
            c.drawRightString(A4[0] - 20 * mm, 10 * mm, page)
        c.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"{t['title']} {app['reference']}", author="RIP", subject="Preliminary assessment")
    s: list = [b.p(t["product"], "muted"), b.p(f"{t['title']} — {app['reference']}", "title"), Spacer(1, 4),
               b.p(t["disclaimer"], "muted", color="#D94B52"), Spacer(1, 10)]

    s += [b.p(t["app"], "h2"), b.table([
        [t["ref"], app["reference"]], [t["company"], app["company_name_ar"] if b.rtl else app["company_name_en"]],
        [t["category"], lb(app["service_category"])], [t["status"], lb(app["status"])], [t["cr"], app.get("commercial_registration") or "—"],
        [t["capital"], f"{app['paid_up_capital_sar']:,.0f}" if app.get("paid_up_capital_sar") is not None else "—"],
        [t["hosting"], app.get("data_hosting_location") or "—"]], [50 * mm, 120 * mm], header=False)]

    risk = draft["overall_risk"]
    authored = {"AI": t["ai"], "HUMAN": t["human"], "MIXED": t["mixed"]}.get(draft["authored_by"], draft["authored_by"])
    s += [b.p(t["summary"], "h2"), b.p(f"{t['risk']}: {lb(risk)}", "body", color=SEV.get(risk, "#142238")), Spacer(1, 3),
          b.p(draft["summary_ar"] if b.rtl else draft["summary_en"]), b.p(f"({authored})", "muted")]
    if draft.get("analyst_notes"):
        s += [b.p(t["notes"], "h2"), b.p(draft["analyst_notes"])]

    rows = [[t["sev"], t["cat"], t["finding"], t["evidence"], t["source"]]]
    for f in draft["findings"]:
        src = []
        for c in f["citations"]:
            if c.get("document_code"):
                src.append(f"{c['document_code']} {c.get('version_label', '')} — {c.get('section', '')}"
                           + (f" ({t['page']} {c['page_number']})" if c.get("page_number") else "")
                           + f" [{t['verified'] if c.get('verified') else t['unverified']}]")
            elif c.get("source_type") == "APPLICATION_DOCUMENT":
                src.append(("وثيقة الطلب" if b.rtl else "Application document") + f": {c.get('quote', '')[:80]}")
        ev = f["evidence_ar"] if b.rtl else f["evidence_en"]
        interp = f["interpretation_ar"] if b.rtl else f["interpretation_en"]
        rows.append([b.p(lb(f["severity"]), "cellb", 18 * mm - 12, SEV.get(f["severity"])), lb(f["category"]),
                     (f["title_ar"] if b.rtl else f["title_en"]) + "\n" + f"{t['interp']}: {interp}", ev[:600], "\n".join(src) or "—"])
    s += [b.p(f"{t['findings']} ({len(draft['findings'])})", "h2"), b.table(rows, [18 * mm, 24 * mm, 52 * mm, 42 * mm, 34 * mm])]

    miss = draft.get("missing_documents") or []
    s += [b.p(t["missing"], "h2"), b.p(("، " if b.rtl else ", ").join(lb(m["document_type"]) for m in miss))
          if miss else b.p(t["none"])]

    if reviews:
        rrows = [[t["reviewer"], t["decision"], t["comments"], t["date"]]] + [
            [r["reviewer_name_ar"] if b.rtl else r["reviewer_name_en"], lb(r["decision"]), r["comment"] or "—", r["created_at"][:16].replace("T", " ")]
            for r in reviews]
        s += [b.p(t["comments"], "h2"), b.table(rrows, [36 * mm, 34 * mm, 70 * mm, 30 * mm])]

    s += [b.p(t["limitations"], "h2"), b.p(draft["limitations_ar"] if b.rtl else draft["limitations_en"])]
    meta = draft.get("generation_meta") or {}
    s += [KeepTogether([b.p(t["meta"], "h2"), b.table([
        [t["version"], str(draft["version"])], [t["draft_status"], lb(draft["status"])], [t["authored"], authored],
        [t["model"], f"{meta.get('provider', '')} / {meta.get('model', '')}" + (f" ({t['mock']})" if meta.get("mock") else "")],
        [t["draft_id"], draft["id"]], [t["run"], str(draft.get("agent_run_id") or "—")],
        [t["generated"], datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")], [t["generated_by"], generated_by]],
        [50 * mm, 120 * mm], header=False)])]
    doc.build(s, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
