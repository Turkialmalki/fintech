"""Idempotent seed: `python -m app.seed.run [--reset] [--no-assess]`.

Passwords are never stored in the repository. They come from SEED_ADMIN_PASSWORD / SEED_STAFF_PASSWORD
when set; otherwise each account gets a random password (set it later via the admin console or SQL).
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import secrets
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
from app.seed.portfolio import portfolio
from app.seed.version import SEED_VERSION
from app.services import applications as apps

log = logging.getLogger("rip.seed")
DATA = Path(__file__).parent / "data"
ORG_SLUG = "rip-main"
DOMAIN = os.getenv("SEED_EMAIL_DOMAIN", "rip.sa")

# key -> (email local part, name ar, name en, title ar, title en, roles)
USERS = {
    "admin": ("turki", "تركي المالكي", "Turki Almalki", "مؤسس المنصة ومديرها", "Founder & platform administrator", ["admin"]),
    "supervisor": ("nouf.alharbi", "نوف الحربي", "Nouf Alharbi", "رئيسة فريق المراجعة", "Head of review", ["supervisor"]),
    "analyst": ("abdulaziz.alqahtani", "عبدالعزيز القحطاني", "Abdulaziz Alqahtani", "محلل امتثال أول", "Senior compliance analyst", ["analyst"]),
    "analyst2": ("lama.alshehri", "لمى الشهري", "Lama Alshehri", "محللة امتثال", "Compliance analyst", ["analyst"]),
    "auditor": ("majed.alzahrani", "ماجد الزهراني", "Majed Alzahrani", "مدقق داخلي", "Internal auditor", ["auditor"]),
    "viewer": ("hessa.alghamdi", "حصة الغامدي", "Hessa Alghamdi", "إدارة المخاطر — اطلاع", "Risk management (read-only)", ["viewer"]),
    "guest": ("reviewer", "زائر المنصة", "Guest Reviewer", "محلل امتثال (تجربة)", "Compliance analyst (trial)", ["analyst"]),
}


def email_for(key: str) -> str:
    return f"{USERS[key][0]}@{DOMAIN}"


def _password(key: str) -> str:
    env = os.getenv("SEED_ADMIN_PASSWORD") if key == "admin" else os.getenv("SEED_STAFF_PASSWORD")
    return env or secrets.token_urlsafe(24)


DOCS = [
    ("SAMA-BNPL", "SAMA-BNPL.txt", "قواعد تنظيم شركات الشراء الآن والدفع لاحقاً", "Rules Regulating Buy-Now-Pay-Later Companies",
     "https://rulebook.sama.gov.sa/en/node/6523", "2023.12", date(2023, 12, 1), ["bnpl"]),
    ("SAMA-PAYMENTS", "SAMA-PAYMENTS.txt", "نظام المدفوعات وخدماتها ولائحته التنفيذية — متطلبات الترخيص", "Law of Payments and Payment Services — licensing requirements",
     "https://www.sama.gov.sa/en-US/FAQs/Pages/PaymentsFAQs.aspx", "2022", None, ["payments", "e-money"]),
    ("SAMA-OPENBANKING", "SAMA-OPENBANKING.txt", "متطلبات خدمة بدء الدفع ومعلومات الحساب وإطار المصرفية المفتوحة", "Payment initiation, account information and the Open Banking Framework",
     "https://rulebook.sama.gov.sa/en/entiresection/1544", "2024", date(2022, 11, 1), ["open-banking"]),
    ("SAMA-MICROFINANCE", "SAMA-MICROFINANCE.txt", "قواعد تنظيم شركات التمويل الاستهلاكي المصغر والتمويل الجماعي بالدين", "Consumer Microfinance and Debt Crowdfunding Rules",
     "https://rulebook.sama.gov.sa/en/node/2574", "2019", date(2019, 12, 10), ["lending"]),
    ("SAMA-CSF", "SAMA-CSF.txt", "إطار الأمن السيبراني", "SAMA Cyber Security Framework",
     "https://rulebook.sama.gov.sa/node/3837", "1.0", date(2017, 5, 24), ["cyber"]),
    ("SAMA-AML", "SAMA-AML.txt", "نظام مكافحة غسل الأموال وتمويل الإرهاب ودليل البنك المركزي", "AML/CTF Laws and SAMA AML/CTF Guide",
     "https://rulebook.sama.gov.sa/node/791", "2017", date(2017, 10, 25), ["aml"]),
    ("SDAIA-PDPL", "SDAIA-PDPL.txt", "نظام حماية البيانات الشخصية ولائحته التنفيذية", "Personal Data Protection Law and Implementing Regulations",
     "https://sdaia.gov.sa/en/SDAIA/about/Documents/Personal%20Data%20English%20V2-23April2023-%20Reviewed-.pdf", "2023", date(2023, 9, 14), ["pdpl", "data"]),
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
    d.core_properties.title = path.stem
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
    c.setTitle(path.stem)
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
    org = db.scalar(select(Organization).where(Organization.slug == ORG_SLUG))
    if org is None:
        org = Organization(name_ar="وحدة الامتثال والجاهزية التنظيمية", name_en="Compliance & Regulatory Readiness Unit", slug=ORG_SLUG, is_synthetic=False)
        db.add(org)
    accounts = [(k, email_for(k), *USERS[k][1:], org) for k in USERS]
    org_b = None
    if os.getenv("SEED_SECOND_TENANT") == "1":  # used by the test suite to verify tenant isolation
        org_b = db.scalar(select(Organization).where(Organization.slug == "partner-tenant"))
        if org_b is None:
            org_b = Organization(name_ar="جهة شريكة", name_en="Partner Tenant", slug="partner-tenant", is_synthetic=False)
            db.add(org_b)
        accounts.append(("tenant_b", f"admin@partner.{DOMAIN}", "مدير الجهة الشريكة", "Partner Admin", "مدير", "Admin", ["admin"], org_b))
    db.flush()
    users = {}
    for key, email, ar, en, tar, ten, rcodes, o in accounts:
        u = db.scalar(select(User).where(User.email == email))
        if u is None:
            u = User(email=email, full_name_ar=ar, full_name_en=en, title_ar=tar, title_en=ten,
                     password_hash=hash_password(_password(key)), org_id=o.id)
            db.add(u)
        u.roles = [roles[c] for c in rcodes]
        users[key] = u
    db.flush()
    return {"org": org, "org_b": org_b, "users": users}


def seed_regulatory(db, admin) -> None:
    p = principal_from_user(admin)
    for code, fname, tar, ten, url, ver, pub, tags in DOCS:
        ingest_regulatory_document(db, p, filename=fname, data=(DATA / fname).read_bytes(), document_code=code,
                                   title_ar=tar, title_en=ten, classification="public", version_label=ver,
                                   publication_date=pub, tags=tags, source=url, is_synthetic=False)
    for r in REQUIREMENTS:
        if not db.scalar(select(RegulatoryRequirement).where(RegulatoryRequirement.code == r["code"], RegulatoryRequirement.org_id == admin.org_id)):
            db.add(RegulatoryRequirement(org_id=admin.org_id, is_synthetic=False, **r))
    db.flush()


def seed_governance(db, org) -> None:
    if db.scalar(select(AIModel).where(AIModel.org_id == org.id)):
        return
    m_mock = AIModel(org_id=org.id, name="Rule-based analysis engine", provider="mock", model_id="rules-engine-v1", version="1",
                     hosting="self_hosted", owner="فريق المنصة", approval_status="APPROVED", deployment_status="PRODUCTION",
                     is_active=True, capabilities={"json_schema": True, "tool_calling": False, "probed": True},
                     notes="Deterministic checks and extractive summaries; used when no language model is configured.")
    m_qwen = AIModel(org_id=org.id, name="Qwen 2.5 72B Instruct", provider="qwen", model_id="Qwen/Qwen2.5-72B-Instruct", version="2.5",
                     hosting="self_hosted", base_url_env="QWEN_BASE_URL", context_window=32768, owner="فريق الذكاء الاصطناعي",
                     approval_status="PENDING", deployment_status="STAGING", notes="Self-hosted via vLLM. Capabilities not yet probed.")
    m_llama = AIModel(org_id=org.id, name="Llama 3.3 70B Instruct", provider="llama", model_id="meta-llama/Llama-3.3-70B-Instruct",
                      version="3.3", hosting="self_hosted", base_url_env="LLAMA_BASE_URL", context_window=131072,
                      owner="فريق الذكاء الاصطناعي", approval_status="PENDING", deployment_status="NOT_DEPLOYED",
                      notes="Alternative provider. Requires --enable-auto-tool-choice on vLLM for tool calling.")
    m_emb = AIModel(org_id=org.id, name="Hashing n-gram embedder", provider="mock", model_id="hashing-ngram-v1", purpose="embedding",
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
    db.add(SystemSetting(org_id=None, key="seed.version", value={"value": SEED_VERSION}, description="Seeded content version."))


def all_companies() -> list[dict]:
    base = [{**c, "days_ago": 40 - i * 6, "assignee": "analyst" if i % 2 == 0 else "analyst2"} for i, c in enumerate(COMPANIES)]
    return base + portfolio()


def seed_applications(db, ctx) -> dict:
    org, users = ctx["org"], ctx["users"]
    analyst = users["analyst"]
    p = principal_from_user(analyst)
    created = {}
    for c in all_companies():
        existing = db.scalar(select(FintechApplication).where(FintechApplication.org_id == org.id,
                                                              FintechApplication.company_name_en == c["company_name_en"]))
        if existing:
            created[c["key"]] = existing
            continue
        fields = {k: v for k, v in c.items() if k not in ("key", "documents", "status", "outcome", "days_ago", "assignee")}
        fields["service_category"] = ServiceCategory(fields["service_category"])
        a = FintechApplication(org_id=org.id, reference=apps.new_reference(db), created_by_id=analyst.id, is_synthetic=False,
                               assigned_analyst_id=users.get(c["assignee"], analyst).id, **fields)
        db.add(a)
        db.flush()
        apps.event(db, a, p, "CREATED")
        for dtype, body in c["documents"].items():
            apps.upload_document(db, p, a, filename=f"{c['key']}_{dtype.lower()}.txt", data=body.encode(), document_type=DocumentType(dtype))
        if c["status"] != "DRAFT":
            apps.transition(db, p, a, S.SUBMITTED, reason="submitted by applicant")
        created[c["key"]] = a
    db.flush()
    return created


DOC_AR = {"COMMERCIAL_REGISTRATION": "السجل التجاري", "BUSINESS_PLAN": "خطة العمل", "FINANCIAL_STATEMENTS": "القوائم المالية المدققة",
          "AML_CTF_POLICY": "سياسة مكافحة غسل الأموال", "CYBERSECURITY_POLICY": "سياسة الأمن السيبراني",
          "DATA_PROTECTION_POLICY": "سياسة حماية البيانات الشخصية", "GOVERNANCE_STRUCTURE": "هيكل الحوكمة",
          "OUTSOURCING_AGREEMENTS": "اتفاقيات الإسناد", "CONSUMER_PROTECTION_POLICY": "سياسة حماية العملاء",
          "RISK_MANAGEMENT_FRAMEWORK": "إطار إدارة المخاطر"}


def seed_assessments(ctx, created) -> None:
    """Runs the REAL agent workflow (MCP + LangGraph) for the pipeline, then records human decisions.

    Resumable: applications that already have a draft are skipped, so an interrupted bootstrap continues where it stopped.
    """
    from app.agents.graph import create_run, execute_run
    from app.models import AssessmentDraft
    from app.services import assessments as asmt
    from app.services import rules

    plan = {"tamweel": "pending", "openbank": "comment", "remit": "approve", "lend": "info"}
    plan |= {c["key"]: c["outcome"] for c in portfolio() if c["outcome"] in ("approve", "info", "pending", "close")}
    with session_scope() as db:
        users = {k: principal_from_user(db.get(User, ctx["users"][k].id)) for k in ctx["users"] if ctx["users"][k] is not None}
        done = {a for (a,) in db.execute(select(AssessmentDraft.application_id).distinct())}
    for key in plan:
        if key in created and created[key].id not in done:
            run_id = create_run(users["analyst"], created[key].id)
            execute_run(run_id, users["analyst"])
    with session_scope() as db:
        for key, outcome in plan.items():
            if key not in created:
                continue
            d = db.scalar(select(AssessmentDraft).where(AssessmentDraft.application_id == created[key].id)
                          .order_by(AssessmentDraft.version.desc()).limit(1))
            if d is None or d.status != "PENDING_REVIEW":
                continue
            app = db.get(FintechApplication, created[key].id)
            if outcome == "comment":
                asmt.decide(db, users["analyst"], d, "COMMENT", "تم التحقق من استشهادات متطلبات الموافقة، بانتظار مراجعة المشرفة.", False)
            elif outcome in ("approve", "close"):
                asmt.decide(db, users["supervisor"], d, "APPROVE_FOR_NEXT_STAGE",
                            "اكتملت المراجعة الأولية والوثائق مستوفاة؛ يُحال إلى مرحلة المراجعة التالية.", True)
                if outcome == "close":
                    apps.transition(db, users["supervisor"], app, S.CLOSED, reason="اكتملت مراحل المراجعة")
            elif outcome == "info":
                missing = [m["document_type"] for m in rules.check_required_documents(db, app)["missing"]]
                ask = "، ".join(DOC_AR.get(m, m) for m in missing) or "توضيح ضوابط نقل البيانات خارج المملكة"
                asmt.decide(db, users["analyst"], d, "REQUEST_INFORMATION", f"يرجى تقديم: {ask}.", True)
    backdate(created)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM system_settings WHERE key = 'seed.assessed' AND org_id IS NULL"))
        conn.execute(text("INSERT INTO system_settings (id, org_id, key, value, description, created_at, updated_at) "
                          "VALUES (gen_random_uuid(), NULL, 'seed.assessed', CAST(:v AS jsonb), 'Seed assessments complete.', now(), now())"),
                     {"v": '{"value": "%s"}' % SEED_VERSION})


def backdate(created) -> None:
    """Spread the pipeline over its real timeline (seeded objects are created in one go)."""
    import random

    now = datetime.now(timezone.utc)
    days = {c["key"]: c["days_ago"] for c in all_companies()}
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_logs SET created_at = :t WHERE action IN ('regulatory_document_indexed', 'regulatory_document_uploaded')"),
                     {"t": now - timedelta(days=185)})
        for key, a in created.items():
            rnd = random.Random(key)
            t0 = now - timedelta(days=days.get(key, 10), hours=rnd.randint(0, 9))
            sub = t0 + timedelta(hours=rnd.randint(6, 30))
            ran = sub + timedelta(hours=rnd.randint(2, 20))
            rev = ran + timedelta(hours=rnd.randint(18, 90))
            p = {"id": a.id, "t0": t0, "sub": sub, "ran": ran, "rev": min(rev, now - timedelta(hours=1))}
            conn.execute(text("UPDATE fintech_applications SET created_at=:t0, updated_at=:rev, "
                              "submitted_at = CASE WHEN submitted_at IS NULL THEN NULL ELSE :sub END WHERE id=:id"), p)
            conn.execute(text("UPDATE application_documents SET created_at=:t0, updated_at=:t0 WHERE application_id=:id"), p)
            conn.execute(text("UPDATE agent_runs SET created_at=:ran, started_at=:ran, "
                              "finished_at = :ran + (COALESCE(duration_ms,0) * interval '1 millisecond') WHERE application_id=:id"), p)
            conn.execute(text("UPDATE assessment_drafts SET created_at=:ran, updated_at=:rev WHERE application_id=:id"), p)
            conn.execute(text("UPDATE assessment_findings f SET created_at=:ran FROM assessment_drafts d "
                              "WHERE f.draft_id=d.id AND d.application_id=:id"), p)
            conn.execute(text("UPDATE analyst_reviews SET created_at=:rev WHERE application_id=:id"), p)
            conn.execute(text("UPDATE application_comments SET created_at=:rev WHERE application_id=:id"), p)
            conn.execute(text("""UPDATE audit_logs l SET created_at = CASE
                WHEN l.action IN ('application_created','application_document_uploaded','extracted_profile_stored') THEN :t0
                WHEN l.action LIKE 'review_%' OR l.action IN ('information_requested','comment_added','analyst_assigned') THEN :rev
                WHEN l.action = 'status_changed' AND l.details->>'to' IN ('SUBMITTED') THEN :sub
                WHEN l.action = 'status_changed' AND l.details->>'to' IN ('AI_ANALYSIS','PENDING_HUMAN_REVIEW') THEN :ran
                WHEN l.action = 'status_changed' THEN :rev
                ELSE :ran END
                WHERE l.resource_id = CAST(:id AS text)
                   OR l.resource_id IN (SELECT CAST(id AS text) FROM assessment_drafts WHERE application_id = :id)
                   OR l.resource_id IN (SELECT CAST(id AS text) FROM agent_runs WHERE application_id = :id)
                   OR l.resource_id IN (SELECT CAST(id AS text) FROM application_documents WHERE application_id = :id)"""), p)
            conn.execute(text("UPDATE audit_logs SET created_at = :ran WHERE details->>'run_id' IN "
                              "(SELECT CAST(id AS text) FROM agent_runs WHERE application_id = :id)"), p)
            conn.execute(text("""UPDATE application_events e SET created_at = CASE
                WHEN e.event_type='CREATED' THEN :t0 WHEN e.to_status='SUBMITTED' THEN :sub
                WHEN e.to_status IN ('AI_ANALYSIS','PENDING_HUMAN_REVIEW') THEN :ran ELSE :rev END WHERE e.application_id=:id"""), p)


def seed_assessments_from_db() -> None:
    """Continue seeded assessments for already-seeded data (e.g. after an interrupted first run)."""
    from app.models import AgentRun

    with session_scope() as db:
        org = db.scalar(select(Organization).where(Organization.slug == ORG_SLUG))
        by_email = {u.email: u for u in db.scalars(select(User).where(User.org_id == org.id))}
        users = {k: by_email[email_for(k)] for k in USERS if email_for(k) in by_email}
        created = {}
        for c in all_companies():
            a = db.scalar(select(FintechApplication).where(FintechApplication.org_id == org.id,
                                                           FintechApplication.company_name_en == c["company_name_en"]))
            if a:
                created[c["key"]] = a
        db.query(AgentRun).filter(AgentRun.org_id == org.id, AgentRun.status == "FAILED").delete()
    seed_assessments({"users": users}, created)


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
        admin = ctx["users"]["admin"]
        seeded = db.scalar(select(RegulatoryRequirement.id).where(RegulatoryRequirement.org_id == admin.org_id).limit(1))
        if not seeded:
            seed_regulatory(db, admin)
        seed_governance(db, ctx["org"])
        created = seed_applications(db, ctx)
        key_note = ""
        if not db.scalar(select(McpApiKey).where(McpApiKey.org_id == ctx["org"].id)):
            raw, prefix, h = generate_api_key()
            db.add(McpApiKey(org_id=ctx["org"].id, name="Read-only integration key", key_prefix=prefix, key_hash=h,
                             user_id=ctx["users"]["analyst"].id, scopes=["read"]))
            key_note = raw
    if not a.no_assess and not seeded:
        seed_assessments(ctx, created)
    log.info("seed complete (version %s)", SEED_VERSION)
    if key_note and os.getenv("SEED_PRINT_KEYS") == "1":
        print("MCP read-only API key (shown once):", key_note)


if __name__ == "__main__":
    main()
