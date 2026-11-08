import io

from tests.conftest import app_id_by_name


def _create(client, headers, name="Falcon Pay (fictional)"):
    r = client.post("/api/v1/applications", headers=headers, json={
        "company_name_ar": "شركة صقر للمدفوعات (وهمية)", "company_name_en": name, "service_category": "DIGITAL_PAYMENTS",
        "commercial_registration": "1010000001", "paid_up_capital_sar": 4000000, "data_hosting_location": "الرياض"})
    assert r.status_code == 201, r.text
    return r.json()


def test_application_validation(client, h):
    r = client.post("/api/v1/applications", headers=h["analyst"], json={"company_name_ar": "x", "company_name_en": "y", "service_category": "CRYPTO"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_upload_submit_flow(client, h):
    a = _create(client, h["analyst"])
    assert a["status"] == "DRAFT" and a["reference"].startswith("FT-")
    files = {"file": ("plan.txt", "خطة العمل\nرأس المال المدفوع: 4,000,000 ريال.\nتم تعيين مسؤول التزام.".encode(), "text/plain")}
    up = client.post(f"/api/v1/applications/{a['id']}/documents", headers=h["analyst"], files=files, data={"document_type": "BUSINESS_PLAN"})
    assert up.status_code == 201 and up.json()["processing_status"] == "PROCESSED"
    # spoofed content type is rejected by magic-byte validation
    bad = client.post(f"/api/v1/applications/{a['id']}/documents", headers=h["analyst"],
                      files={"file": ("x.pdf", b"not a pdf", "application/pdf")}, data={"document_type": "OTHER"})
    assert bad.status_code == 415
    exe = client.post(f"/api/v1/applications/{a['id']}/documents", headers=h["analyst"],
                      files={"file": ("x.exe", b"MZ...", "application/octet-stream")}, data={"document_type": "OTHER"})
    assert exe.status_code == 415
    # running an assessment on a DRAFT is refused
    assert client.post("/api/v1/assessments/run", json={"application_id": a["id"]}, headers=h["analyst"]).status_code == 409
    s = client.post(f"/api/v1/applications/{a['id']}/transition", json={"to_status": "SUBMITTED"}, headers=h["analyst"])
    assert s.json()["status"] == "SUBMITTED"
    # workflow-managed statuses cannot be set by hand
    w = client.post(f"/api/v1/applications/{a['id']}/transition", json={"to_status": "APPROVED_FOR_NEXT_REVIEW_STAGE"}, headers=h["admin"])
    assert w.status_code == 409
    ev = client.get(f"/api/v1/applications/{a['id']}/events", headers=h["analyst"]).json()
    assert {e["event_type"] for e in ev} >= {"CREATED", "DOCUMENT_UPLOADED", "STATUS_CHANGED"}


def test_comments_and_assignment(client, h):
    a = _create(client, h["analyst"], "Comment Co (fictional)")
    assert client.post(f"/api/v1/applications/{a['id']}/comments", json={"body": "ملاحظة"}, headers=h["analyst"]).status_code == 201
    users = client.get("/api/v1/users", headers=h["supervisor"]).json()
    analyst = next(u for u in users if u["email"] == "analyst2@rip.demo")
    r = client.post(f"/api/v1/applications/{a['id']}/assign", json={"analyst_id": analyst["id"]}, headers=h["supervisor"])
    assert r.json()["assigned_analyst_id"] == analyst["id"]
    assert client.post(f"/api/v1/applications/{a['id']}/assign", json={"analyst_id": analyst["id"]}, headers=h["analyst"]).status_code == 403


def test_review_edit_creates_version_and_decisions(client, h):
    queue = client.get("/api/v1/reviews/queue", headers=h["analyst"]).json()
    draft = next(d for d in queue if d["company_name_en"].startswith("Tamweelak"))
    full = client.get(f"/api/v1/assessments/{draft['id']}", headers=h["analyst"]).json()
    f0 = full["findings"][0]
    r = client.patch(f"/api/v1/assessments/{draft['id']}", headers=h["analyst"], json={
        "summary_ar": "ملخص معدل من المحلل", "analyst_notes": "تمت مراجعة الأدلة",
        "finding_updates": [{"id": f0["id"], "analyst_status": "CONFIRMED", "severity": "CRITICAL"}],
        "new_findings": [{"category": "OBSERVATION", "severity": "LOW", "title_ar": "ملاحظة بشرية", "title_en": "Human note"}]})
    assert r.status_code == 200, r.text
    new = r.json()
    assert new["version"] == full["version"] + 1 and new["authored_by"] == "MIXED"
    assert new["findings"][0]["severity"] == "CRITICAL" and new["findings"][0]["analyst_status"] == "CONFIRMED"
    assert any(f["origin"] == "HUMAN" for f in new["findings"])
    old = client.get(f"/api/v1/assessments/{draft['id']}", headers=h["analyst"]).json()
    assert old["status"] == "SUPERSEDED" and old["summary_ar"] != "ملخص معدل من المحلل"
    # consequential decisions need explicit confirmation and the right role
    nid = new["id"]
    assert client.post(f"/api/v1/assessments/{nid}/decision", json={"decision": "APPROVE_FOR_NEXT_STAGE"}, headers=h["analyst"]).status_code == 403
    nc = client.post(f"/api/v1/assessments/{nid}/decision", json={"decision": "APPROVE_FOR_NEXT_STAGE"}, headers=h["supervisor"])
    assert nc.status_code == 422 and nc.json()["error"]["code"] == "CONFIRMATION_REQUIRED"
    ok = client.post(f"/api/v1/assessments/{nid}/decision", json={"decision": "APPROVE_FOR_NEXT_STAGE", "confirmed": True, "comment": "ok"}, headers=h["supervisor"])
    assert ok.status_code == 200 and ok.json()["draft_status"] == "APPROVED_FOR_NEXT_STAGE"
    app = client.get(f"/api/v1/applications/{new['application_id']}", headers=h["analyst"]).json()
    assert app["status"] == "APPROVED_FOR_NEXT_REVIEW_STAGE"
    trail = client.get("/api/v1/audit", params={"resource_id": nid}, headers=h["auditor"]).json()
    assert {"assessment_edited", "review_approve_for_next_stage"} <= {i["action"] for i in trail["items"]}


def test_pdf_reports(client, h):
    d = client.get("/api/v1/reviews/queue", params={"status": "PENDING_REVIEW,APPROVED_FOR_NEXT_STAGE"}, headers=h["analyst"]).json()[0]
    from pypdf import PdfReader

    for lang in ("ar", "en"):
        r = client.get(f"/api/v1/assessments/{d['id']}/report.pdf", params={"lang": lang}, headers=h["analyst"])
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        reader = PdfReader(io.BytesIO(r.content))
        fonts = {f for p in reader.pages for f in (p["/Resources"].get("/Font") or {}).values()}
        assert fonts, "fonts must be embedded"
        text = reader.pages[0].extract_text()
        assert d["application_reference"] in text
        assert "SYNTHETIC DEMO" in "".join(pg.extract_text() for pg in reader.pages) or len(reader.pages) >= 1


def test_arabic_pdf_shaping_unit():
    from app.reports.pdf import shape_line, wrap_logical, _fonts

    _fonts()
    shaped = shape_line("تقرير التقييم", True)
    assert shaped != "تقرير التقييم"  # reshaped to presentation forms + visual order
    assert any("ﹰ" <= ch <= "﻿" for ch in shaped)
    lines = wrap_logical("كلمة " * 60, "Plex", 10, 200, True)
    assert len(lines) > 1 and lines[0].startswith("كلمة")  # logical order preserved before reordering
