"""Idempotent demo seed: `python -m app.seed.run [--reset] [--no-assess]`.

Everything created here is SYNTHETIC and labelled as such.
"""
from __future__ import annotations

import argparse
import io
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, text

from app.api.deps import principal_from_user
from app.core.db import Base, engine, session_scope
from app.core.security import PERMISSIONS, ROLES, generate_api_key, hash_password
from app.models import (
    AIModel,
    AIUseCase,
    ApplicationStatus as S,
    DocumentType,
    FintechApplication,
    GovernanceControl,
    McpApiKey,
    Organization,
    Permission,
    RegulatoryRequirement,
    Role,
    ServiceCategory,
    SystemSetting,
    User,
)
from app.rag.index import ingest_regulatory_document
from app.seed.companies import COMPANIES, REQUIREMENTS
from app.services import applications as apps

log = logging.getLogger("rip.seed")
DATA = Path(__file__).parent / "data"
PASSWORD = "Demo@2026!"

USERS = [
    ("admin@rip.demo", "سارة الدوسري", "Sarah Al-Dossary", "مديرة النظام", "Platform administrator", ["admin"]),
    ("supervisor@rip.demo", "نورة العتيبي", "Noura Al-Otaibi", "مشرفة المراجعة", "Review supervisor", ["supervisor"]),
    ("analyst@rip.demo", "فيصل القحطاني", "Faisal Al-Qahtani", "محلل أول", "Senior analyst", ["analyst"]),
    ("analyst2@rip.demo", "ريم الشهري", "Reem Al-Shehri", "محللة", "Analyst", ["analyst"]),
    ("auditor@rip.demo", "خالد الزهراني", "Khalid Al-Zahrani", "مدقق داخلي", "Internal auditor", ["auditor"]),
    ("viewer@rip.demo", "منى الغامدي", "Mona Al-Ghamdi", "مطّلعة", "Viewer", ["viewer"]),
]

GOV_CONTROLS = [
    ("NIST_AI_RMF", "GOVERN", "حوكمة مخاطر الذكاء الاصطناعي", "Govern AI risk", "السياسات والأدوار والمساءلة.", "Policies, roles and accountability."),
    ("NIST_AI_RMF", "MAP", "تحديد السياق والمخاطر", "Map context and risks", "فهم سياق الاستخدام والأثر.", "Understand context of use and impact."),
    ("NIST_AI_RMF", "MEASURE", "القياس والتقييم", "Measure", "تقييم الأداء والموثوقية والانحياز.", "Assess performance, reliability and bias."),
    ("NIST_AI_RMF", "MANAGE", "إدارة المخاطر", "Manage", "معالجة المخاطر ومتابعتها.", "Treat and monitor risks."),
    ("ISO_IEC_42001", "Cl.6", "التخطيط وتقييم المخاطر", "Planning and AI risk assessment", "مجال مرجعي لنظام إدارة الذكاء الاصطناعي.", "Reference area of the AI management system."),
    ("ISO_IEC_42001", "Cl.8", "التشغيل وتقييم أثر النظام", "Operation and AI system impact assessment", "مجال مرجعي.", "Reference area."),
    ("ISO_IEC_42001", "Cl.9", "تقييم الأداء", "Performance evaluation", "مجال مرجعي.", "Reference area."),
    ("SA_DATA_PROTECTION", "PDPL-REF-1", "الأساس النظامي للمعالجة", "Lawful basis for processing", "مجال مرجعي — يُتحقق منه مقابل النص الرسمي.", "Reference area — verify against the official text."),
    ("SA_DATA_PROTECTION", "PDPL-REF-2", "نقل البيانات خارج المملكة", "Cross-border data transfer", "مجال مرجعي — يُتحقق منه مقابل النص الرسمي.", "Reference area — verify against the official text."),
    ("FS_CYBER_TECH", "CYB-REF-1", "إدارة الهويات والصلاحيات", "Identity and access management", "مجال مرجعي لأطر الأمن السيبراني في القطاع المالي.", "Reference area for financial-sector cybersecurity frameworks."),
    ("FS_CYBER_TECH", "TECH-REF-1", "إدارة الإسناد والتقنية", "Technology and outsourcing governance", "مجال مرجعي.", "Reference area."),
]


def make_docx(path: Path) -> bytes:
    import docx

    d = docx.Document()
    d.core_properties.title = "Synthetic Conduct Guidelines for BNPL Services"
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if line.startswith("Section "):
            d.add_heading(line, level=2)
        else:
            d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def make_pdf(path: Path) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Synthetic Supervisory Note on Cloud Hosting and Outsourcing")
    y = 800
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Section ") and y < 760:
            c.showPage()  # one section per page so page numbers are meaningful
            y = 800
        words, cur = line.split(), ""
        for w in words:
            if len(cur) + len(w) > 95:
                c.drawString(40, y, cur)
                y -= 16
                cur = ""
            cur += w + " "
        c.drawString(40, y, cur)
        y -= 18
    c.save()
    return buf.getvalue()


def reset() -> None:
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        conn.execute(text(f"TRUNCATE {tables} CASCADE"))


def seed_identity(db) -> dict:
    perms = {}
    for code, desc in PERMISSIONS.items():
        p = db.scalar(select(Permission).where(Permission.code == code)) or Permission(code=code, description=desc)
        db.add(p)
        perms[code] = p
    roles = {}
    for code, r in ROLES.items():
        role = db.scalar(select(Role).where(Role.code == code)) or Role(code=code, name_ar=r["ar"], name_en=r["en"])
        role.permissions = [perms[p] for p in r["perms"]]
        db.add(role)
        roles[code] = role
    db.flush()
    org = db.scalar(select(Organization).where(Organization.slug == "demo-supervision"))
    if org is None:
        org = Organization(name_ar="وحدة الرقابة التجريبية", name_en="Demo Supervisory Unit", slug="demo-supervision", is_synthetic=True)
        db.add(org)
    org_b = db.scalar(select(Organization).where(Organization.slug == "tenant-b"))
    if org_b is None:
        org_b = Organization(name_ar="جهة تجريبية ثانية", name_en="Second Demo Tenant", slug="tenant-b", is_synthetic=True)
        db.add(org_b)
    db.flush()
    users = {}
    for email, ar, en, tar, ten, rcodes in USERS + [("admin@tenantb.demo", "مدير الجهة الثانية", "Tenant B Admin", "مدير", "Admin", ["admin"])]:
        u = db.scalar(select(User).where(User.email == email))
        if u is None:
            u = User(email=email, full_name_ar=ar, full_name_en=en, title_ar=tar, title_en=ten, password_hash=hash_password(PASSWORD),
                     org_id=org_b.id if email.endswith("tenantb.demo") else org.id)
            db.add(u)
        u.roles = [roles[c] for c in rcodes]
        users[email] = u
    db.flush()
    return {"org": org, "org_b": org_b, "users": users}


def seed_regulatory(db, admin) -> None:
    p = principal_from_user(admin)
    v1 = (DATA / "RIP-SYN-001.txt").read_text(encoding="utf-8").replace(
        "خمسة ملايين ريال سعودي (5,000,000 ريال)", "ثلاثة ملايين ريال سعودي (3,000,000 ريال)")
    common = dict(source="RIP demonstration corpus (synthetic)", is_synthetic=True)
    ingest_regulatory_document(db, p, filename="RIP-SYN-001-v1.txt", data=v1.encode(), document_code="RIP-SYN-001",
                               title_ar="الإطار التجريبي لتقييم طلبات خدمات التقنية المالية (اصطناعية)",
                               title_en="Synthetic Fintech Application Assessment Framework", classification="internal",
                               version_label="2025.1", publication_date=date(2025, 1, 15), effective_date=date(2025, 3, 1), tags=["framework"], **common)
    ingest_regulatory_document(db, p, filename="RIP-SYN-001.txt", data=(DATA / "RIP-SYN-001.txt").read_bytes(), document_code="RIP-SYN-001",
                               title_ar="الإطار التجريبي لتقييم طلبات خدمات التقنية المالية (اصطناعية)",
                               title_en="Synthetic Fintech Application Assessment Framework", classification="internal",
                               version_label="2026.1", publication_date=date(2026, 2, 1), effective_date=date(2026, 4, 1), tags=["framework"], **common)
    ingest_regulatory_document(db, p, filename="RIP-SYN-002.docx", data=make_docx(DATA / "RIP-SYN-002.txt"), document_code="RIP-SYN-002",
                               title_ar="إرشادات سلوكية تجريبية لخدمات الشراء الآن والدفع لاحقاً (اصطناعية)",
                               title_en="Synthetic BNPL Conduct Guidelines", classification="public", version_label="2026.1",
                               publication_date=date(2026, 1, 10), tags=["bnpl", "conduct"], **common)
    ingest_regulatory_document(db, p, filename="RIP-SYN-003.txt", data=(DATA / "RIP-SYN-003.txt").read_bytes(), document_code="RIP-SYN-003",
                               title_ar="الدليل التجريبي لخدمات المصرفية المفتوحة (اصطناعية)", title_en="Synthetic Open Banking Guide",
                               classification="internal", version_label="2025.2", effective_date=date(2025, 9, 1), tags=["open-banking"], **common)
    ingest_regulatory_document(db, p, filename="RIP-SYN-004.pdf", data=make_pdf(DATA / "RIP-SYN-004.txt"), document_code="RIP-SYN-004",
                               title_ar="مذكرة رقابية تجريبية حول الاستضافة السحابية والإسناد (مقيدة، اصطناعية)",
                               title_en="Synthetic Supervisory Note on Cloud Hosting and Outsourcing", classification="restricted",
                               version_label="2026.1", tags=["cloud", "outsourcing"], **common)
    for r in REQUIREMENTS:
        if not db.scalar(select(RegulatoryRequirement).where(RegulatoryRequirement.code == r["code"], RegulatoryRequirement.org_id == admin.org_id)):
            db.add(RegulatoryRequirement(org_id=admin.org_id, is_synthetic=True, **r))
    db.flush()


def seed_governance(db, org) -> None:
    if db.scalar(select(AIModel).where(AIModel.org_id == org.id)):
        return
    m_mock = AIModel(org_id=org.id, name="Deterministic mock", provider="mock", model_id="deterministic-mock-v1", version="1",
                     hosting="self_hosted", owner="فريق المنصة", approval_status="APPROVED", deployment_status="PRODUCTION",
                     is_active=True, capabilities={"json_schema": True, "tool_calling": False, "probed": True},
                     notes="Used when no model credentials are configured. Produces extractive, rule-based output only.")
    m_qwen = AIModel(org_id=org.id, name="Qwen 2.5 72B Instruct", provider="qwen", model_id="Qwen/Qwen2.5-72B-Instruct", version="2.5",
                     hosting="self_hosted", base_url_env="QWEN_BASE_URL", context_window=32768, owner="فريق الذكاء الاصطناعي",
                     approval_status="PENDING", deployment_status="STAGING", notes="Self-hosted via vLLM. Capabilities not yet probed.")
    m_llama = AIModel(org_id=org.id, name="Llama 3.3 70B Instruct", provider="llama", model_id="meta-llama/Llama-3.3-70B-Instruct",
                      version="3.3", hosting="self_hosted", base_url_env="LLAMA_BASE_URL", context_window=131072,
                      owner="فريق الذكاء الاصطناعي", approval_status="PENDING", deployment_status="NOT_DEPLOYED",
                      notes="Alternative provider. Requires --enable-auto-tool-choice on vLLM for tool calling.")
    m_emb = AIModel(org_id=org.id, name="Hashing n-gram embedder (mock)", provider="mock", model_id="hashing-ngram-v1", purpose="embedding",
                    hosting="self_hosted", owner="فريق المنصة", approval_status="APPROVED", deployment_status="PRODUCTION", is_active=True,
                    notes="Lexical feature hashing; replace with a multilingual embedding model (e.g. BGE-M3) in production.")
    db.add_all([m_mock, m_qwen, m_llama, m_emb])
    db.flush()
    db.add_all([
        AIUseCase(org_id=org.id, code="UC-01", name_ar="التقييم الأولي لطلبات التقنية المالية", name_en="Preliminary fintech application assessment",
                  business_purpose_ar="دعم المحللين بتحديد الفجوات والمخاطر المحتملة مع الأدلة.", business_purpose_en="Support analysts in identifying potential gaps and risks with evidence.",
                  owner="إدارة الرقابة", model_id=m_mock.id, risk_classification="HIGH", data_classification="CONFIDENTIAL",
                  approval_status="APPROVED", deployment_status="PRODUCTION", monitoring_status="MONITORED",
                  control_mappings=[{"framework": "NIST_AI_RMF", "control_ref": "GOVERN", "status": "MAPPED", "note": "Human-in-the-loop review"},
                                    {"framework": "NIST_AI_RMF", "control_ref": "MEASURE", "status": "PARTIAL", "note": "RAG evaluation dataset"},
                                    {"framework": "ISO_IEC_42001", "control_ref": "Cl.8", "status": "PLANNED", "note": ""}]),
        AIUseCase(org_id=org.id, code="UC-02", name_ar="البحث التنظيمي الذكي", name_en="Regulatory intelligence search",
                  business_purpose_ar="البحث الدلالي في الوثائق التنظيمية مع استشهادات قابلة للتحقق.", business_purpose_en="Semantic search with verifiable citations.",
                  owner="إدارة السياسات", model_id=m_emb.id, risk_classification="MEDIUM", data_classification="INTERNAL",
                  approval_status="APPROVED", deployment_status="PRODUCTION", monitoring_status="MONITORED",
                  control_mappings=[{"framework": "FS_CYBER_TECH", "control_ref": "CYB-REF-1", "status": "MAPPED", "note": "Permission-aware retrieval"}]),
        AIUseCase(org_id=org.id, code="UC-03", name_ar="استخراج بيانات الوثائق المرفوعة", name_en="Submitted document data extraction",
                  business_purpose_ar="استخراج بيانات منظمة من وثائق مقدمي الطلبات.", business_purpose_en="Structured extraction from applicant documents.",
                  owner="إدارة الرقابة", model_id=m_qwen.id, risk_classification="MEDIUM", data_classification="CONFIDENTIAL",
                  approval_status="PENDING", deployment_status="STAGING", monitoring_status="NOT_MONITORED",
                  control_mappings=[{"framework": "SA_DATA_PROTECTION", "control_ref": "PDPL-REF-2", "status": "UNDER_REVIEW", "note": "Self-hosted in KSA region"}]),
    ])
    for fw, ref, tar, ten, dar, den in GOV_CONTROLS:
        db.add(GovernanceControl(org_id=org.id, framework=fw, reference=ref, title_ar=tar, title_en=ten, description_ar=dar, description_en=den))
    db.add(SystemSetting(org_id=None, key="platform.disclaimer", value={"value": "synthetic-demo"},
                         description="Demo environment: all regulatory content is synthetic."))


def seed_applications(db, ctx) -> dict:
    org, users = ctx["org"], ctx["users"]
    analyst = users["analyst@rip.demo"]
    p = principal_from_user(analyst)
    created = {}
    now = datetime.now(timezone.utc)
    for i, c in enumerate(COMPANIES):
        existing = db.scalar(select(FintechApplication).where(FintechApplication.org_id == org.id,
                                                              FintechApplication.company_name_en == c["company_name_en"]))
        if existing:
            created[c["key"]] = existing
            continue
        fields = {k: v for k, v in c.items() if k not in ("key", "documents", "status")}
        fields["service_category"] = ServiceCategory(fields["service_category"])
        a = FintechApplication(org_id=org.id, reference=apps.new_reference(db), created_by_id=analyst.id, is_synthetic=True,
                               assigned_analyst_id=(users["analyst@rip.demo"] if i % 2 == 0 else users["analyst2@rip.demo"]).id, **fields)
        a.created_at = now - timedelta(days=40 - i * 6)
        db.add(a)
        db.flush()
        apps.event(db, a, p, "CREATED")
        for dtype, body in c["documents"].items():
            apps.upload_document(db, p, a, filename=f"{c['key']}_{dtype.lower()}.txt", data=body.encode(), document_type=DocumentType(dtype))
        if c["status"] != "DRAFT":
            apps.transition(db, p, a, S.SUBMITTED, reason="seed")
        created[c["key"]] = a
    db.flush()
    return created


def seed_assessments(ctx, created) -> None:
    """Runs the REAL agent workflow (MCP + LangGraph) for several applications, then records human decisions."""
    from app.agents.graph import create_run, execute_run
    from app.models import AssessmentDraft
    from app.services import assessments as asmt

    with session_scope() as db:
        analyst = principal_from_user(db.get(User, ctx["users"]["analyst@rip.demo"].id))
        supervisor = principal_from_user(db.get(User, ctx["users"]["supervisor@rip.demo"].id))
    for key in ("tamweel", "openbank", "remit", "lend"):
        run_id = create_run(analyst, created[key].id)
        execute_run(run_id, analyst)
    with session_scope() as db:
        def latest(key):
            return db.scalar(select(AssessmentDraft).where(AssessmentDraft.application_id == created[key].id)
                             .order_by(AssessmentDraft.version.desc()).limit(1))
        d = latest("openbank")
        asmt.decide(db, analyst, d, "COMMENT", "تم التحقق من استشهادات متطلبات الموافقة، بانتظار مراجعة المشرفة.", False)
        d = latest("remit")
        asmt.decide(db, supervisor, d, "APPROVE_FOR_NEXT_STAGE", "اكتملت المراجعة الأولية؛ يُحال إلى مرحلة المراجعة التالية.", True)
        d = latest("lend")
        asmt.decide(db, analyst, d, "REQUEST_INFORMATION", "يرجى تقديم سياسة حماية العملاء وإطار إدارة المخاطر وهيكل الحوكمة.", True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--no-assess", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level="INFO")
    if a.reset:
        reset()
    with session_scope() as db:
        ctx = seed_identity(db)
        admin = ctx["users"]["admin@rip.demo"]
        seeded = db.scalar(select(RegulatoryRequirement.id).where(RegulatoryRequirement.org_id == admin.org_id).limit(1))
        if not seeded:
            seed_regulatory(db, admin)
        seed_governance(db, ctx["org"])
        created = seed_applications(db, ctx)
        key_note = ""
        if not db.scalar(select(McpApiKey).where(McpApiKey.org_id == ctx["org"].id)):
            raw, prefix, h = generate_api_key()
            db.add(McpApiKey(org_id=ctx["org"].id, name="Demo read-only key", key_prefix=prefix, key_hash=h,
                             user_id=ctx["users"]["analyst@rip.demo"].id, scopes=["read"]))
            key_note = raw
    if not a.no_assess and not seeded:
        seed_assessments(ctx, created)
    print("Seed complete. Demo password for all users:", PASSWORD)
    if key_note:
        print("Demo MCP read-only API key (shown once):", key_note)


if __name__ == "__main__":
    main()
