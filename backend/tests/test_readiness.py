"""Public readiness check: no login, nothing stored, uploads validated, every requirement cites its source."""
import io

AML = """سياسة مكافحة غسل الأموال وتمويل الإرهاب — شركة دانة للدفع الآجل
تعتمد الشركة النهج القائم على المخاطر، وتجري تقييم المخاطر سنوياً حسب العملاء والمنتجات والقنوات والمناطق الجغرافية.
تطبق الشركة إجراءات العناية الواجبة واعرف عميلك، بما في ذلك التحقق من الهوية الوطنية من مصدر موثوق، والعناية الواجبة المعززة للحالات عالية المخاطر.
يتولى مسؤول الإبلاغ (MLRO) الإبلاغ عن العمليات المشتبه بها إلى الإدارة العامة للتحريات المالية دون تنبيه العميل.
تحتفظ الشركة بالسجلات ووثائق العناية الواجبة مدة عشر سنوات من انتهاء العلاقة، وتفحص العملاء مقابل قوائم العقوبات.
يحصل جميع الموظفين على التدريب السنوي على مكافحة غسل الأموال، وتخضع السياسة لمراجعة مستقلة.""".encode()

PLAN = """خطة العمل ودراسة الجدوى — شركة دانة للدفع الآجل
نموذج العمل: تقدم الشركة خدمة الشراء الآن والدفع لاحقاً عبر تطبيق ومنصة رقمية تقسم المشتريات على أربع دفعات دون رسوم على العميل.
السوق والعملاء المستهدفون: الأفراد في المملكة من عمر 18 سنة فأكثر عبر شبكة من المتاجر الشريكة.
التوقعات المالية: نتوقع إيرادات من عمولة التجار تبلغ 12 مليون ريال في السنة الثالثة.
رأس المال المدفوع: 6,000,000 ريال سعودي. التوظيف: 46 موظفاً بنسبة توطين 52%. تم تعيين مسؤول التزام مستقل.
الحوكمة: مجلس إدارة من خمسة أعضاء ولجنة المراجعة ولجنة المخاطر، والرئيس التنفيذي يرفع تقاريره إلى المجلس، والهيكل التنظيمي مرفق.""".encode()

FIN = """القوائم المالية المدققة للسنة المنتهية في 31 ديسمبر 2025 — شركة دانة للدفع الآجل
تقرير المراجع الخارجي: في رأينا تعرض القوائم المالية بعدل المركز المالي للشركة.
قائمة المركز المالي: إجمالي الأصول 9,450,000 ريال، الأصول المتداولة 7,120,000 ريال.
إجمالي الخصوم 2,310,000 ريال، الخصوم المتداولة 1,840,000 ريال.
حقوق الملكية: رأس المال 6,000,000 ريال، الأرباح المبقاة 1,140,000 ريال.
قائمة الدخل: الإيرادات 4,380,000 ريال، صافي الربح 1,140,000 ريال للسنة المالية.""".encode()


def _check(client, files=(), **form):
    data = {"service_category": "BNPL", "company_name": "شركة دانة للدفع الآجل", **form}
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
    assert body["key_rules"] and all(k["evidence"] for k in body["key_rules"])


def test_real_documents_are_accepted_and_improve_score(client):
    base = _check(client, paid_up_capital_sar="6000000").json()["score"]
    files = [("aml.txt", AML, "text/plain"), ("plan.txt", PLAN, "text/plain"), ("fin.txt", FIN, "text/plain")]
    r = _check(client, files, paid_up_capital_sar="6000000", data_hosting_location="الرياض").json()
    status = {a["filename"]: a for a in r["documents"]["analysed"]}
    assert all(a["status"] == "ACCEPTED" for a in status.values()), status
    assert status["aml.txt"]["assigned_types"] == ["AML_CTF_POLICY"]
    assert "GOVERNANCE_STRUCTURE" in r["documents"]["present"]
    assert r["score"] > base and not r["consistency"]
    assert next(i for i in r["requirements"] if i["code"] == "BNPL-CAP")["outcome"] == "MET"


def test_fake_and_invalid_uploads_are_rejected(client):
    files = [
        ("short.txt", "سياسة مكافحة غسل الأموال".encode(), "text/plain"),                      # a title, not a document
        ("filler.txt", ("غسل الأموال " * 300).encode(), "text/plain"),                          # keyword stuffing
        ("recipe.txt", ("طريقة تحضير الكبسة باللحم والأرز والبهارات مع الطماطم والبصل " * 8).encode(), "text/plain"),  # unrelated
        ("fake.pdf", b"this is not a pdf at all", "application/pdf"),                            # wrong magic bytes
        ("x.exe", b"MZ" + b"\0" * 300, "application/octet-stream"),                             # disallowed type
        ("aml.txt", AML, "text/plain"), ("aml-copy.txt", AML, "text/plain"),                     # duplicate
    ]
    r = _check(client, files, paid_up_capital_sar="6000000")
    assert r.status_code == 200, r.text
    st = {a["filename"]: a for a in r.json()["documents"]["analysed"]}
    for name in ("short.txt", "filler.txt", "recipe.txt", "fake.pdf", "x.exe", "aml-copy.txt"):
        assert st[name]["status"] == "REJECTED" and st[name]["reason_ar"], name
    assert st["aml.txt"]["status"] == "ACCEPTED"
    assert r.json()["documents"]["present"] == ["AML_CTF_POLICY"]


def test_thin_policy_is_partial_not_met(client):
    thin = ("سياسة الأمن السيبراني للشركة. " + "تلتزم الشركة بحماية أنظمتها ومعلوماتها وتطوير قدراتها التقنية باستمرار وفق أفضل الممارسات المتبعة في القطاع المالي. " * 4
            + "نستخدم التشفير لحماية البيانات.").encode()
    r = _check(client, [("cyber.txt", thin, "text/plain")], paid_up_capital_sar="6000000").json()
    a = r["documents"]["analysed"][0]
    assert a["status"] == "PARTIAL" and a["elements_missing"]
    csf = next(i for i in r["requirements"] if i["code"] == "CSF-01")
    assert csf["outcome"] == "INSUFFICIENT_INFORMATION" and "استكمل" in csf["action_ar"]


def test_consistency_checks(client):
    r = _check(client, [("fin.txt", FIN, "text/plain")], paid_up_capital_sar="9000000", company_name="شركة أخرى تماماً").json()
    msgs = " ".join(c["ar"] for c in r["consistency"])
    assert "لا يطابق" in msgs and "اسم الشركة" in msgs


def test_offshore_hosting_risk(client):
    r = _check(client, service_category="DIGITAL_WALLET", paid_up_capital_sar="1500000", data_hosting_location="Abroad").json()
    assert any(x["code"] == "RISK-HOST-01" for x in r["risks"])
    assert next(i for i in r["requirements"] if i["code"] == "EMI-CAP")["outcome"] == "POTENTIAL_GAP"


def test_docx_upload_is_read(client):
    import docx

    d = docx.Document()
    for line in AML.decode().splitlines():
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    r = _check(client, [("aml.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")]).json()
    assert r["documents"]["analysed"][0]["status"] == "ACCEPTED"
