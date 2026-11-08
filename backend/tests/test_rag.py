from app.rag.chunk import chunk_blocks
from app.rag.extract import Block, extract
from app.rag.normalize import detect_language, normalize, tokenize


def test_arabic_normalization():
    assert normalize("إِلَى الأَمَانَة") == "الي الامانه"
    assert normalize("٢٠٢٦") == "2026"
    assert "تمويل" in tokenize("والتمويل الرقمي")
    assert detect_language("Article 2 المادة") in ("mixed", "ar", "en")
    assert detect_language("hello world") == "en"


def test_extraction_preserves_pages_and_sections():
    ex = extract("x.txt", "المادة 1 - النطاق\nنص أول.\fالمادة 2 - رأس المال\nنص ثان عن رأس المال.".encode())
    assert len(ex.pages) == 2
    secs = {(b.section, b.page) for b in ex.blocks}
    assert ("المادة 1 - النطاق", 1) in secs and ("المادة 2 - رأس المال", 2) in secs


def test_chunks_do_not_cross_sections():
    blocks = [Block(1, "Section 1", "Section 1\n" + "Alpha sentence. " * 100), Block(2, "Section 2", "Section 2\nBeta.")]
    chunks = chunk_blocks(blocks, max_chars=300)
    assert len(chunks) > 3
    assert all(c.section in ("Section 1", "Section 2") for c in chunks)
    assert chunks[-1].section == "Section 2" and chunks[-1].page == 2


def test_hybrid_search_returns_real_content(client, h):
    r = client.post("/api/v1/regulatory/search", json={"query": "ما الحد الأدنى لرأس المال المدفوع للمحافظ الرقمية"}, headers=h["analyst"]).json()
    top = r["results"][0]
    assert top["document_code"] == "RIP-SYN-001" and "المادة 2" in top["section"]
    assert "خمسة ملايين" in top["text"]  # active version (2026.1)
    assert top["version_label"] == "2026.1"


def test_english_search(client, h):
    r = client.post("/api/v1/regulatory/search", json={"query": "late payment charges compound", "mode": "keyword"}, headers=h["analyst"]).json()
    assert r["results"][0]["document_code"] == "RIP-SYN-002"


def test_version_aware_retrieval(client, h):
    q = {"query": "ثلاثة ملايين ريال رأس المال المدفوع", "mode": "keyword", "top_k": 10}
    active = client.post("/api/v1/regulatory/search", json=q, headers=h["analyst"]).json()["results"]
    assert all(x["version_status"] == "ACTIVE" for x in active)
    allv = client.post("/api/v1/regulatory/search", json={**q, "include_superseded": True}, headers=h["analyst"]).json()["results"]
    assert any(x["version_status"] == "SUPERSEDED" and "ثلاثة ملايين" in x["text"] for x in allv)


def test_permission_aware_retrieval(client, h):
    q = {"query": "cloud hosting approval data transfer risk assessment", "top_k": 10}
    analyst = client.post("/api/v1/regulatory/search", json=q, headers=h["analyst"]).json()["results"]
    sup = client.post("/api/v1/regulatory/search", json=q, headers=h["supervisor"]).json()["results"]
    assert not any(x["classification"] == "restricted" for x in analyst)
    assert any(x["classification"] == "restricted" for x in sup)
    docs = client.get("/api/v1/regulatory/documents", headers=h["analyst"]).json()
    assert docs["restricted_hidden"] == 1


def test_rag_answer_citations_are_verified(client, h):
    r = client.post("/api/v1/rag/query", json={"query": "ما مدة صلاحية موافقة العميل في المصرفية المفتوحة؟"}, headers=h["analyst"]).json()
    assert r["insufficient_evidence"] is False
    assert r["citations"] and all(c["verified"] for c in r["citations"])
    assert r["citations"][0]["document_code"] == "RIP-SYN-003"
    assert r["sources"][0]["page_number"] == 1  # pagination preserved from the form-feed document


def test_rag_insufficient_evidence(client, h):
    r = client.post("/api/v1/rag/query", json={"query": "جدول مباريات كرة القدم للموسم القادم"}, headers=h["analyst"]).json()
    assert r["insufficient_evidence"] is True and r["citations"] == []


def test_citation_validator():
    from app.rag.answer import quote_supported

    chunk = "يجب ألا يقل رأس المال المدفوع لمقدمي خدمات المدفوعات الرقمية عن خمسة ملايين ريال سعودي."
    assert quote_supported("يجب ألا يقل رأس المال المدفوع لمقدمي خدمات المدفوعات الرقمية", chunk)
    assert not quote_supported("يجب أن يكون رأس المال مليار ريال وتعيين عشرين مديراً", chunk)


def test_upload_regulatory_document_new_version(client, h):
    files = {"file": ("t.txt", "Section 1 - Test\nThe synthetic test rule requires quarterly reporting.".encode(), "text/plain")}
    r = client.post("/api/v1/regulatory/documents", files=files, data={"document_code": "RIP-TEST-1", "title_en": "Test"}, headers=h["admin"])
    assert r.status_code == 201, r.text
    files2 = {"file": ("t2.txt", "Section 1 - Test\nThe synthetic test rule requires monthly reporting.".encode(), "text/plain")}
    r2 = client.post("/api/v1/regulatory/documents", files=files2, data={"document_code": "RIP-TEST-1"}, headers=h["admin"]).json()
    assert r2["version"]["version_number"] == 2 and r2["document"]["version_count"] == 2
    hits = client.post("/api/v1/regulatory/search", json={"query": "synthetic test rule reporting", "mode": "keyword"}, headers=h["admin"]).json()["results"]
    assert "monthly" in hits[0]["text"]
    assert client.post("/api/v1/regulatory/documents", files=files, data={"document_code": "X"}, headers=h["analyst"]).status_code == 403


def test_evaluation_dataset_runs(client, h):
    r = client.post("/api/v1/governance/evaluations/run", headers=h["admin"]).json()
    m = r["metrics"]
    assert r["sample_count"] >= 10 and r["is_mock"] is True
    assert m["recall_at_k"] >= 0.8 and m["mrr"] >= 0.7 and m["citation_correctness"] >= 0.6
