from tests.conftest import app_id_by_name


def test_login_and_me(client, h):
    r = client.get("/api/v1/auth/me", headers=h["analyst"])
    assert r.status_code == 200
    assert r.json()["role_codes"] == ["analyst"]
    assert "reviews:approve" not in r.json()["permissions"]


def test_login_failure_is_generic_and_audited(client, h):
    r = client.post("/api/v1/auth/login", json={"email": "analyst@rip.demo", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
    r2 = client.post("/api/v1/auth/login", json={"email": "nobody@rip.demo", "password": "wrong"})
    assert r2.json()["error"]["message"] == r.json()["error"]["message"]  # no user enumeration
    logs = client.get("/api/v1/audit", params={"action": "login_failed"}, headers=h["admin"]).json()
    assert logs["total"] >= 1


def test_missing_and_invalid_token(client):
    assert client.get("/api/v1/applications").status_code == 401
    assert client.get("/api/v1/applications", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_refresh_token_cannot_be_used_as_access(client):
    r = client.post("/api/v1/auth/login", json={"email": "viewer@rip.demo", "password": "Demo@2026!"}).json()
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r['refresh_token']}"}).status_code == 401
    new = client.post("/api/v1/auth/refresh", json={"refresh_token": r["refresh_token"]})
    assert new.status_code == 200


def test_rbac_permissions(client, h):
    body = {"company_name_ar": "شركة اختبار", "company_name_en": "Test Co", "service_category": "BNPL"}
    assert client.post("/api/v1/applications", json=body, headers=h["viewer"]).status_code == 403
    assert client.get("/api/v1/audit", headers=h["analyst"]).status_code == 403
    assert client.get("/api/v1/audit", headers=h["auditor"]).status_code == 200
    assert client.post("/api/v1/governance/evaluations/run", headers=h["analyst"]).status_code == 403
    assert client.put("/api/v1/ai/config", json={"provider": "mock"}, headers=h["analyst"]).status_code == 403
    denied = client.get("/api/v1/audit", params={"action": "permission_denied"}, headers=h["admin"]).json()
    assert denied["total"] >= 1


def test_tenant_isolation_applications(client, h):
    app_id = app_id_by_name(client, h["analyst"], "Tamweelak")
    assert client.get(f"/api/v1/applications/{app_id}", headers=h["tenant_b"]).status_code == 404
    assert client.get("/api/v1/applications", headers=h["tenant_b"]).json()["total"] == 0
    assert client.patch(f"/api/v1/applications/{app_id}", json={"city": "x"}, headers=h["tenant_b"]).status_code == 404


def test_tenant_isolation_regulatory_and_search(client, h):
    assert client.get("/api/v1/regulatory/documents", headers=h["tenant_b"]).json()["items"] == []
    r = client.post("/api/v1/regulatory/search", json={"query": "رأس المال المدفوع"}, headers=h["tenant_b"]).json()
    assert r["results"] == []
    drafts = client.get("/api/v1/reviews/queue", headers=h["analyst"]).json()
    assert client.get(f"/api/v1/assessments/{drafts[0]['id']}", headers=h["tenant_b"]).status_code == 404


def test_tenant_isolation_mcp_tools(principal):
    from app.core.errors import NotFound
    from app.core.db import session_scope
    from app.models import FintechApplication
    from app.services.tools import execute
    from sqlalchemy import select
    import pytest

    with session_scope() as db:
        app_id = str(db.scalar(select(FintechApplication.id).limit(1)))
    with pytest.raises(NotFound):
        execute("get_fintech_application", {"application_id": app_id}, principal("admin@tenantb.demo"))


def test_security_headers_and_request_id(client):
    r = client.get("/api/v1/system/info")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-request-id"]


def test_health(client):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").json()["checks"]["database"] == "ok"
