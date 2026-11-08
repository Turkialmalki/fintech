"""LangGraph orchestration of the fintech assessment workflow.

    start ─► document_intelligence ─► regulatory_research ─► compliance_gap ─► risk_analysis
          ─► assessment_reporting ─► human_review_checkpoint ─► END

The graph always stops at the human checkpoint: it can submit a draft for review, but only a
human user can record decisions (enforced in services.assessments.decide).
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from functools import partial

from langgraph.graph import END, StateGraph
from langgraph.types import RetryPolicy

from app.agents import nodes as N
from app.agents.runtime import AgentToolClient, Budget, BudgetExceeded, StepRecorder, ToolCallFailed
from app.ai.providers.base import ProviderError
from app.ai.service import current_org, current_run, get_ai
from app.core.config import settings
from app.core.db import session_scope
from app.core.security import Principal
from app.models import AgentRun, ApplicationStatus as S, FintechApplication
from app.services import applications as apps
from app.services import audit

log = logging.getLogger("rip.agents")


def _retryable(e: Exception) -> bool:
    return (isinstance(e, ProviderError) and e.retryable) or (isinstance(e, ToolCallFailed) and e.retryable)


RETRY = RetryPolicy(max_attempts=settings.agent_retry_attempts + 1, initial_interval=0.5, retry_on=_retryable)


def _wrap(agent: str, fn, ctx: N.Ctx):
    async def node(state: N.AState) -> N.AState:
        ctx.budget.steps += 1
        ctx.budget.check()
        return await fn(state, ctx)

    node.__name__ = agent
    return node


async def orchestrator_start(state: N.AState, ctx: N.Ctx) -> N.AState:
    t0 = time.perf_counter()
    app = await ctx.tools.call("orchestrator", "get_fintech_application", {"application_id": state["application_id"]})
    hist = await ctx.tools.call("orchestrator", "get_assessment_history", {"application_id": state["application_id"]})
    ctx.recorder.record("orchestrator", "NODE", "start", duration_ms=int((time.perf_counter() - t0) * 1000),
                        output={"reference": app["reference"], "category": app["service_category"], "previous_drafts": len(hist["drafts"])})
    return {"application": app, "notes": [f"previous drafts: {len(hist['drafts'])}"]}


async def human_review_checkpoint(state: N.AState, ctx: N.Ctx) -> N.AState:
    res = await ctx.tools.call("orchestrator", "submit_for_human_review", {"draft_id": state["draft_id"]})
    ctx.recorder.record("orchestrator", "DECISION", "human_review_checkpoint",
                        output={"status": res["status"], "note": "Workflow paused for human review. No decision taken by AI."})
    return {"review_status": res["status"]}


async def document_intelligence_and_persist(state: N.AState, ctx: N.Ctx) -> N.AState:
    out = await N.document_intelligence(state, ctx)
    # Deterministic system step (not an LLM tool): store the validated extracted profile on the
    # application so the deterministic risk rules can use it. Audited.
    with session_scope() as db:
        app = db.get(FintechApplication, uuid.UUID(state["application_id"]))
        app.extracted_profile = out.get("profile", {})
        audit.record(db, category="AGENT", action="extracted_profile_stored", org_id=app.org_id, actor_type="AGENT",
                     resource_type="application", resource_id=app.id, details={"fields": sorted(app.extracted_profile)})
    return out


def build_graph(ctx: N.Ctx):
    g = StateGraph(N.AState)
    g.add_node("start", _wrap("orchestrator", orchestrator_start, ctx), retry_policy=RETRY)
    g.add_node("document_intelligence", _wrap("document_intelligence", document_intelligence_and_persist, ctx), retry_policy=RETRY)
    g.add_node("regulatory_research", _wrap("regulatory_research", N.regulatory_research, ctx), retry_policy=RETRY)
    g.add_node("compliance_gap", _wrap("compliance_gap", N.compliance_gap, ctx), retry_policy=RETRY)
    g.add_node("risk_analysis", _wrap("risk_analysis", N.risk_analysis, ctx), retry_policy=RETRY)
    g.add_node("assessment_reporting", _wrap("assessment_reporting", N.assessment_reporting, ctx), retry_policy=RETRY)
    g.add_node("human_review_checkpoint", _wrap("orchestrator", human_review_checkpoint, ctx))
    g.set_entry_point("start")
    order = ["start", "document_intelligence", "regulatory_research", "compliance_gap", "risk_analysis",
             "assessment_reporting", "human_review_checkpoint"]
    for a, b in zip(order, order[1:]):
        g.add_edge(a, b)
    g.add_edge("human_review_checkpoint", END)
    return g.compile()


GRAPH_DESCRIPTION = {
    "nodes": ["start", "document_intelligence", "regulatory_research", "compliance_gap", "risk_analysis",
              "assessment_reporting", "human_review_checkpoint"],
    "agents": {k: sorted(v) for k, v in N.AGENT_TOOLS.items()},
}


def create_run(principal: Principal, application_id: uuid.UUID) -> uuid.UUID:
    ai = get_ai()
    with session_scope() as db:
        app = apps.get_app(db, principal, application_id)
        if app.status in (S.DRAFT, S.CLOSED, S.APPROVED_FOR_NEXT_REVIEW_STAGE, S.AI_ANALYSIS):
            from app.core.errors import AppError

            raise AppError(f"Cannot run an assessment while the application is {app.status.value}",
                           "لا يمكن تشغيل التقييم في الحالة الحالية للطلب (يجب تقديم الطلب أولاً)", status_code=409,
                           code="INVALID_STATE")
        run = AgentRun(org_id=principal.org_id, application_id=app.id, triggered_by_id=principal.user_id, status="QUEUED",
                       ai_provider=ai.cfg.provider, ai_model=ai.llm.model, tool_transport=settings.agent_tool_transport,
                       budget=Budget().to_dict())
        db.add(run)
        if app.status in (S.SUBMITTED, S.DOCUMENT_PROCESSING, S.ADDITIONAL_INFORMATION_REQUIRED, S.PENDING_HUMAN_REVIEW):
            if app.status == S.ADDITIONAL_INFORMATION_REQUIRED:
                apps.transition(db, principal, app, S.SUBMITTED, reason="resubmitted for assessment", system=True)
            apps.transition(db, principal, app, S.AI_ANALYSIS, reason="AI assessment started", system=True)
        db.flush()
        audit.record(db, category="AGENT", action="assessment_run_started", principal=principal, resource_type="agent_run",
                     resource_id=run.id, details={"application_id": str(app.id), "provider": ai.cfg.provider, "model": ai.llm.model})
        return run.id


async def _execute(run_id: uuid.UUID, principal: Principal) -> None:
    ai = get_ai()
    agent_principal = Principal(user_id=principal.user_id, org_id=principal.org_id, email=principal.email, roles=principal.roles,
                                permissions=principal.permissions, actor_type="AGENT", scopes=frozenset({"read", "write"}))
    budget = Budget()
    recorder = StepRecorder(run_id, principal.org_id)
    with session_scope() as db:
        run = db.get(AgentRun, run_id)
        run.status = "RUNNING"
        run.started_at = datetime.now(timezone.utc)
        app_id = run.application_id
    current_org.set(principal.org_id)
    current_run.set(run_id)
    t0 = time.perf_counter()
    status, error, final = "AWAITING_REVIEW", "", {}
    try:
        async with AgentToolClient(agent_principal, recorder, budget, str(run_id), allowed_tools=N.AGENT_TOOLS) as tools:
            ctx = N.Ctx(tools, ai, recorder, budget)
            graph = build_graph(ctx)
            final = await asyncio.wait_for(
                graph.ainvoke({"run_id": str(run_id), "application_id": str(app_id), "locale": "ar"},
                              {"recursion_limit": settings.agent_max_steps}),
                timeout=settings.agent_timeout_seconds)
    except (BudgetExceeded, asyncio.TimeoutError) as e:
        status, error = "FAILED", f"budget/timeout: {e}"
    except Exception as e:  # recorded with full context — never swallowed
        log.exception("agent run failed")
        status, error = "FAILED", f"{type(e).__name__}: {e}"
        recorder.record("orchestrator", "ERROR", "run_failed", status="ERROR", error=error)
    with session_scope() as db:
        run = db.get(AgentRun, run_id)
        run.status = status
        run.error = error[:2000]
        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = int((time.perf_counter() - t0) * 1000)
        run.budget = budget.to_dict()
        run.cost_usd = round(run.tokens_in / 1000 * settings.ai_cost_per_1k_input + run.tokens_out / 1000 * settings.ai_cost_per_1k_output, 6)
        run.final_state = {k: final.get(k) for k in ("draft_id", "draft_version", "review_status", "missing_data", "injection_flags",
                                                     "profile") if k in final}
        if status == "FAILED":
            app = db.get(FintechApplication, app_id)
            if app and app.status == S.AI_ANALYSIS:
                apps.transition(db, agent_principal, app, S.SUBMITTED, reason="AI assessment failed", system=True)
        audit.record(db, category="AGENT", action="assessment_run_finished", principal=agent_principal, resource_type="agent_run",
                     resource_id=run_id, outcome="SUCCESS" if status != "FAILED" else "FAILURE",
                     details={"status": status, "error": error[:300], "budget": budget.to_dict()})


def execute_run(run_id: uuid.UUID, principal: Principal) -> None:
    """Synchronous entry point (background task / worker / tests)."""
    asyncio.run(_execute(run_id, principal))
