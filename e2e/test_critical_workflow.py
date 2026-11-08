"""End-to-end critical workflow through the real UI (Arabic, RTL) against a running stack.

Run:  E2E_BASE=http://localhost:3000 E2E_API=http://localhost:8000 pytest -q e2e
Covers: login → create application → upload documents → admin uploads a synthetic regulatory document →
indexing → submit → run AI assessment (agents call MCP tools) → evidence/citations displayed → analyst edits
→ supervisor decision with confirmation → audit history contains every step.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import uuid

import pytest
from playwright.sync_api import Page, expect, sync_playwright

BASE = os.getenv("E2E_BASE", "http://localhost:3000")
API = os.getenv("E2E_API", "http://localhost:8000")
PWD = os.environ["RIP_E2E_PASSWORD"]


def api(path: str, token: str | None = None, body: dict | None = None, method: str | None = None):
    req = urllib.request.Request(f"{API}/api/v1{path}", data=json.dumps(body).encode() if body is not None else None,
                                 method=method or ("POST" if body is not None else "GET"),
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    return json.load(urllib.request.urlopen(req))


def ui_login(page: Page, email: str):
    page.context.clear_cookies()
    page.context.add_cookies([{"name": "rip_locale", "value": "ar", "url": BASE}])
    page.goto(f"{BASE}/login")
    page.evaluate("() => sessionStorage.clear()")
    expect(page.locator("html")).to_have_attribute("dir", "rtl")
    page.get_by_label("البريد الإلكتروني").fill(email)
    page.get_by_label("كلمة المرور").fill(PWD)
    page.get_by_role("button", name="دخول").click()
    expect(page.get_by_role("heading", level=1)).to_contain_text("مرحباً")


@pytest.fixture(scope="module")
def page():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        yield pg
        b.close()
        assert not errors, f"uncaught page errors: {errors}"


def test_critical_workflow(page: Page, tmp_path):
    suffix = uuid.uuid4().hex[:6]
    company_en = f"E2E Pay {suffix} (fictional)"

    # 1-2. analyst authenticates and creates an application
    ui_login(page, "abdulaziz.alqahtani@rip.sa")
    page.get_by_role("navigation", name="main").get_by_role("link", name="طلبات التقنية المالية").click()
    page.get_by_role("link", name="طلب جديد").click()
    page.get_by_label("اسم الشركة بالعربية").fill(f"شركة اختبار {suffix} (وهمية)")
    page.get_by_label("اسم الشركة بالإنجليزية").fill(company_en)
    page.get_by_label("رقم السجل التجاري").fill("1010123456")
    page.get_by_label("فئة الخدمة").select_option("DIGITAL_WALLET")
    page.get_by_label("رأس المال المدفوع (ريال)").fill("2500000")
    page.get_by_label("موقع استضافة البيانات").fill("Singapore")
    page.get_by_role("button", name="إنشاء الطلب").click()
    expect(page.get_by_role("heading", level=1)).to_contain_text(f"شركة اختبار {suffix}")
    app_url = page.url

    # 3. upload application documents
    page.get_by_role("tab", name=re.compile("الوثائق")).click()
    plan = tmp_path / "business_plan.txt"
    plan.write_text("وثيقة اصطناعية.\nخطة العمل\nرأس المال المدفوع: 2,500,000 ريال.\nتتم استضافة البيانات في سنغافورة.\n"
                    "لا يوجد حالياً مسؤول التزام.", encoding="utf-8")
    page.get_by_label("نوع الوثيقة").select_option("BUSINESS_PLAN")
    page.locator('input[type="file"]').set_input_files(str(plan))
    expect(page.get_by_text("تم رفع الوثيقة ومعالجتها")).to_be_visible()
    expect(page.get_by_text("خطة العمل").first).to_be_visible()

    # 4-5. admin uploads a synthetic regulatory document and it gets indexed
    admin = api("/auth/login", body={"email": "turki@rip.sa", "password": PWD})["access_token"]
    ui_login(page, "turki@rip.sa")
    page.goto(f"{BASE}/knowledge")
    page.get_by_role("button", name="رفع وثيقة تنظيمية").click()
    page.get_by_label("رمز الوثيقة").fill(f"RIP-E2E-{suffix}")
    page.get_by_label("العنوان بالعربية").fill("وثيقة اختبار اصطناعية للمحافظ الرقمية")
    reg = tmp_path / "reg.txt"
    reg.write_text(f"وثيقة اصطناعية للاختبار.\nالمادة 1 - حدود الأرصدة\nيجب ألا يتجاوز رصيد المحفظة الرقمية للعميل الفرد مبلغ عشرين ألف ريال في بيئة الاختبار {suffix}.",
                   encoding="utf-8")
    page.locator('input[type="file"]').set_input_files(str(reg))
    page.get_by_role("button", name="رفع", exact=True).click()
    expect(page.get_by_text("تمت فهرسة الوثيقة")).to_be_visible()
    hits = api("/regulatory/search", admin, {"query": f"رصيد المحفظة الرقمية للعميل الفرد {suffix}", "mode": "keyword"})["results"]
    assert hits and hits[0]["document_code"] == f"RIP-E2E-{suffix}"

    # 6-9. analyst submits and runs the AI assessment; agents execute and call MCP tools
    ui_login(page, "abdulaziz.alqahtani@rip.sa")
    page.goto(app_url)
    page.get_by_role("button", name="تقديم الطلب").click()
    expect(page.get_by_text("تم تقديم الطلب")).to_be_visible()
    page.get_by_role("button", name="تشغيل التقييم الذكي").click()
    expect(page.get_by_text("بانتظار المراجعة", exact=True).first).to_be_visible(timeout=60_000)
    page.get_by_role("link", name="فتح مساحة التقييم").click()

    # 10-11. draft generated; citations displayed and verifiable
    expect(page.get_by_role("heading", name="مساحة التقييم الذكي")).to_be_visible()
    page.get_by_role("tab", name=re.compile("فجوات محتملة")).click()
    expect(page.get_by_text(re.compile("الحد الأدنى لرأس المال المدفوع")).first).to_be_visible()
    page.get_by_text("تم التحقق من الاقتباس").first.click()  # opens the exact source passage
    expect(page.get_by_text("السياق المحيط")).to_be_visible()
    expect(page.locator("mark").first).to_be_visible()  # quoted sentence highlighted inside the passage
    page.keyboard.press("Escape")
    draft_url = page.url

    # 12. analyst edits the report (creates a new version)
    page.goto(draft_url.replace("/assessments/", "/reviews/"))
    page.get_by_role("button", name="تعديل التقرير").click()
    page.get_by_label("ملاحظات المحلل").fill("راجعت الاستشهادات؛ يلزم طلب سياسة الأمن السيبراني.")
    page.get_by_role("button", name="حفظ كإصدار جديد").click()
    expect(page.get_by_text("تم حفظ إصدار جديد")).to_be_visible()
    expect(page.get_by_text("راجعت الاستشهادات")).to_be_visible()

    # 13. supervisor records the decision with explicit confirmation
    review_url = page.url
    ui_login(page, "nouf.alharbi@rip.sa")
    page.goto(review_url)
    page.get_by_label("ملاحظة المراجع").fill("يُحال للمرحلة التالية بعد استكمال الملاحظات.")
    page.get_by_role("button", name="إحالة للمرحلة التالية").click()
    dialog = page.get_by_role("dialog")
    confirm = dialog.get_by_role("button", name="إحالة للمرحلة التالية")
    expect(confirm).to_be_disabled()  # requires acknowledgement
    dialog.get_by_text("أؤكد أنني راجعت الأدلة").click()
    confirm.click()
    expect(page.get_by_text("تم تسجيل القرار")).to_be_visible()

    # 14. audit history records every relevant action
    sup = api("/auth/login", body={"email": "nouf.alharbi@rip.sa", "password": PWD})["access_token"]
    app_id = app_url.rstrip("/").split("/")[-1]
    app = api(f"/applications/{app_id}", sup)
    assert app["status"] == "APPROVED_FOR_NEXT_REVIEW_STAGE"
    actions = {i["action"] for i in api("/audit?page_size=200", admin)["items"]}
    assert {"application_created", "application_document_uploaded", "regulatory_document_indexed", "status_changed",
            "assessment_run_started", "tool_executed", "assessment_draft_created", "submitted_for_human_review",
            "assessment_edited", "review_approve_for_next_stage", "login_succeeded"} <= actions

    # English mode works and switches direction
    page.get_by_role("button", name="English").click()
    expect(page.locator("html")).to_have_attribute("dir", "ltr")
    expect(page.get_by_role("navigation", name="main").get_by_role("link", name="Fintech applications")).to_be_visible()
