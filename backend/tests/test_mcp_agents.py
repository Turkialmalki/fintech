import asyncio
import uuid

import pytest
from mcp import Client
from sqlalchemy import select

from app.core.db import session_scope
from app.core.security import Principal
from tests.conftest import app_id_by_name

EXPECTED_TOOLS = {"search_regulations", "get_regulation_details", "get_fintech_application", "list_application_documents",
                  "check_required_documents", "analyze_application", "get_risk_indicators", "create_assessment_draft",
                  "get_assessment_history", "submit_for_human_review"}


def mcp_call(principal, tool, args):
    from rip_mcp.server import build_server

    async def go():
        async with Client(build_server(default_principal=principal)) as c:
            listed = await c.list_tools()
            names = {t.name for t in (listed.tools if hasattr(listed, "tools") else listed)}
            r = await c.call_tool(tool, args)
            return names, r.structured_content
    return asyncio.run(go())


def as_mcp(p: Principal, scopes=("read",)) -> Principal:
    return Principal(p.user_id, p.org_id, p.email, p.roles, p.permissions, actor_type="MCP_CLIENT", scopes=frozenset(scopes))


def test_mcp_lists_all_tools_and_executes(principal):
    names, res = mcp_call(as_mcp(principal()), "search_regulations", {"query": "مكافحة غسل الأموال", "top_k": 2})
    assert names == EXPECTED_TOOLS
    assert res["ok"] and res["result"]["results"][0]["document_code"].startswith("SAMA")


def test_mcp_rejects_missing_key():
    from rip_mcp.server import build_server

    async def go():
        async with Client(build_server()) as c:
            return (await c.call_tool("get_regulation_details", {"document_code": "SAMA-BNPL"})).structured_content
    assert asyncio.run(go())["error"]["code"] == "UNAUTHORIZED"


def test_mcp_api_key_auth_and_read_only_default(client, h):
    key = client.post("/api/v1/mcp/keys", json={"name": "test", "scopes": ["read"]}, headers=h["supervisor"]).json()["api_key"]
    from rip_mcp.server import principal_from_api_key

    p = principal_from_api_key(key)
    assert p.actor_type == "MCP_CLIENT" and p.scopes == {"read"}
    app_id = app_id_by_name(client, h["analyst"], "Waha")
    _, ok = mcp_call(p, "check_required_documents", {"application_id": app_id})
    assert ok["ok"] and ok["result"]["missing"]
    _, denied = mcp_call(p, "create_assessment_draft", {"application_id": app_id, "draft": {"findings": []}})
    assert denied["ok"] is False and denied["error"]["code"] == "FORBIDDEN"
    from app.core.errors import Unauthorized

    with pytest.raises(Unauthorized):
        principal_from_api_key("rip_invalid")


def test_mcp_input_validation(principal):
    _, res = mcp_call(as_mcp(principal()), "search_regulations", {"query": "x"})
    assert res is None or res.get("ok") is False


def test_mcp_tool_calls_are_audited(client, h):
    rows = client.get("/api/v1/mcp/executions", headers=h["analyst"]).json()
    assert any(r["action"] == "tool_executed" for r in rows)
    assert any(r["outcome"] == "DENIED" for r in rows)


def _run(principal, app_id):
    from app.agents.graph import create_run, execute_run

    rid = create_run(principal, uuid.UUID(app_id))
    execute_run(rid, principal)
    return rid


def test_agent_workflow_invokes_tools_and_stops_for_human(client, h, principal):
    from app.models import AgentRun, AgentStep

    app_id = app_id_by_name(client, h["analyst"], "Waha")  # contains a planted prompt injection
    rid = _run(principal(), app_id)
    with session_scope() as db:
        run = db.get(AgentRun, rid)
        steps = db.scalars(select(AgentStep).where(AgentStep.run_id == rid)).all()
        assert run.status == "AWAITING_REVIEW", run.error
        assert run.tool_transport == "mcp_inprocess"
        tools = {s.name for s in steps if s.step_type == "TOOL_CALL"}
        assert {"get_fintech_application", "list_application_documents", "search_regulations", "check_required_documents",
                "analyze_application", "get_risk_indicators", "create_assessment_draft", "submit_for_human_review"} <= tools
        assert {s.agent for s in steps} >= {"orchestrator", "document_intelligence", "regulatory_research", "compliance_gap",
                                           "risk_analysis", "assessment_reporting"}
        draft_id = run.final_state["draft_id"]
    d = client.get(f"/api/v1/assessments/{draft_id}", headers=h["analyst"]).json()
    assert d["status"] == "PENDING_REVIEW" and d["application"]["status"] == "PENDING_HUMAN_REVIEW"
    codes = {f["requirement_code"] for f in d["findings"]}
    # the injection did not make the system approve anything; it surfaced as a risk instead
    assert "SEC-INJ-01" in codes
    assert "EMI-CAP" in codes  # capital 1.5M < SAR 2M micro e-money minimum → potential gap
    assert d["generation_meta"]["injection_flags"]
    cited = [c for f in d["findings"] for c in f["citations"] if c["chunk_id"]]
    assert cited and all(c["verified"] for c in cited)
    mcp_audit = client.get("/api/v1/audit", params={"category": "MCP", "page_size": 200}, headers=h["auditor"]).json()
    assert any(i["details"].get("run_id") == str(rid) for i in mcp_audit["items"])


def test_agents_cannot_make_review_decisions(principal):
    from app.core.errors import AppError
    from app.models import AssessmentDraft
    from app.services import assessments as svc

    p = principal("nouf.alharbi@rip.sa")
    agent = Principal(p.user_id, p.org_id, p.email, p.roles, p.permissions, actor_type="AGENT", scopes=frozenset({"read", "write"}))
    with session_scope() as db:
        d = db.scalar(select(AssessmentDraft).where(AssessmentDraft.status == "PENDING_REVIEW", AssessmentDraft.org_id == p.org_id))
        with pytest.raises(AppError) as e:
            svc.decide(db, agent, d, "APPROVE_FOR_NEXT_STAGE", "auto", True)
        assert e.value.code == "HUMAN_REQUIRED"


def test_agent_budget_enforced(client, h, principal, monkeypatch):
    from app.models import AgentRun, FintechApplication

    from app.core.config import settings

    monkeypatch.setattr(settings, "agent_max_tool_calls", 3)
    app_id = app_id_by_name(client, h["analyst"], "Waha")
    rid = _run(principal(), app_id)
    with session_scope() as db:
        run = db.get(AgentRun, rid)
        assert run.status == "FAILED" and "max tool calls" in run.error
        assert db.get(FintechApplication, uuid.UUID(app_id)).status.value == "SUBMITTED"  # reverted, no draft left in limbo


def test_api_run_endpoint_and_run_detail(client, h):
    import time

    app_id = app_id_by_name(client, h["analyst"], "Waha")
    r = client.post("/api/v1/assessments/run", json={"application_id": app_id}, headers=h["analyst"])
    assert r.status_code == 202
    rid = r.json()["run_id"]
    for _ in range(60):
        run = client.get(f"/api/v1/assessments/runs/{rid}", headers=h["analyst"]).json()
        if run["status"] not in ("QUEUED", "RUNNING"):
            break
        time.sleep(0.25)
    assert run["status"] == "AWAITING_REVIEW" and run["steps"]
