"""Public readiness check: no login, nothing stored, every requirement cites its official-source passage."""


def _check(client, files=(), **form):
    data = {"service_category": "BNPL", "company_name": "Test BNPL", **form}
    return client.post("/api/v1/readiness/check", data=data, files=[("files", f) for f in files])


def test_readiness_without_documents_reports_gaps(client):
    r = _check(client, paid_up_capital_sar="3000000")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False and body["level"] == "LOW"
    cap = next(i for i in body["requirements"] if i["code"] == "BNPL-CAP")
    assert cap["outcome"] == "POTENTIAL_GAP" and "5,000,000" in cap["action_ar"]
    assert cap["evidence"]["document_code"] == "SAMA-BNPL" and cap["evidence"]["section"].startswith("المادة 5")
    assert cap["evidence"]["source_url"].startswith("https://rulebook.sama.gov.sa")
    assert "خمسة ملايين" in cap["evidence"]["text"]
    assert body["key_rules"] and all(k["evidence"] for k in body["key_rules"])


def test_readiness_classifies_uploads_and_improves_score(client):
    base = _check(client, paid_up_capital_sar="6000000").json()["score"]
    files = [
        ("aml.txt", "سياسة مكافحة غسل الأموال وتمويل الإرهاب وإجراءات اعرف عميلك والعناية الواجبة".encode(), "text/plain"),
        ("plan.txt", "خطة العمل ودراسة الجدوى. السجل التجاري رقم: 1010000000. الحوكمة ومجلس الإدارة ولجنة المراجعة والهيكل التنظيمي. مسؤول التزام".encode(), "text/plain"),
        ("fin.txt", "القوائم المالية المدققة. رأس المال المدفوع: 6,000,000 ريال".encode(), "text/plain"),
    ]
    r = _check(client, files, paid_up_capital_sar="6000000", data_hosting_location="الرياض").json()
    types = {a["filename"]: a["detected_type"] for a in r["documents"]["analysed"]}
    assert types["aml.txt"] == "AML_CTF_POLICY" and types["fin.txt"] == "FINANCIAL_STATEMENTS"
    assert "GOVERNANCE_STRUCTURE" in r["documents"]["present"]
    assert r["score"] > base
    assert next(i for i in r["requirements"] if i["code"] == "BNPL-CAP")["outcome"] == "MET"


def test_readiness_flags_offshore_hosting_and_validates_files(client):
    r = _check(client, service_category="DIGITAL_WALLET", paid_up_capital_sar="1500000", data_hosting_location="Frankfurt").json()
    assert any(x["code"] == "RISK-HOST-01" for x in r["risks"])
    assert next(i for i in r["requirements"] if i["code"] == "EMI-CAP")["outcome"] == "POTENTIAL_GAP"
    bad = _check(client, [("x.exe", b"MZ...", "application/octet-stream")])
    assert bad.status_code == 415
