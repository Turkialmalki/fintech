"""Agent runtime: execution budget, step recording, and the MCP tool client used by agents."""
from __future__ import annotations

import json
import time
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.db import session_scope
from app.core.security import Principal
from app.models import AgentRun, AgentStep


class BudgetExceeded(RuntimeError):
    pass


class ToolCallFailed(RuntimeError):
    def __init__(self, tool: str, error: dict, retryable: bool = False):
        super().__init__(f"{tool}: {error.get('code')} {error.get('message')}")
        self.tool = tool
        self.error = error
        self.retryable = retryable


@dataclass
class Budget:
    max_steps: int = field(default_factory=lambda: settings.agent_max_steps)
    max_tool_calls: int = field(default_factory=lambda: settings.agent_max_tool_calls)
    max_tokens: int = field(default_factory=lambda: settings.agent_token_budget)
    timeout_s: float = field(default_factory=lambda: settings.agent_timeout_seconds)
    started: float = field(default_factory=time.monotonic)
    steps: int = 0
    tool_calls: int = 0
    tokens: int = 0

    def check(self) -> None:
        if time.monotonic() - self.started > self.timeout_s:
            raise BudgetExceeded(f"execution timeout {self.timeout_s}s exceeded")
        if self.steps > self.max_steps:
            raise BudgetExceeded(f"max steps {self.max_steps} exceeded")
        if self.tool_calls > self.max_tool_calls:
            raise BudgetExceeded(f"max tool calls {self.max_tool_calls} exceeded")
        if self.tokens > self.max_tokens:
            raise BudgetExceeded(f"token budget {self.max_tokens} exceeded")

    def to_dict(self) -> dict:
        return {"max_steps": self.max_steps, "max_tool_calls": self.max_tool_calls, "max_tokens": self.max_tokens,
                "timeout_s": self.timeout_s, "used_steps": self.steps, "used_tool_calls": self.tool_calls,
                "used_tokens": self.tokens, "elapsed_s": round(time.monotonic() - self.started, 2)}


class StepRecorder:
    """Persists each node / tool / LLM step immediately so the UI can follow a run live."""

    def __init__(self, run_id: uuid.UUID, org_id: uuid.UUID):
        self.run_id = run_id
        self.org_id = org_id
        self.seq = 0

    def record(self, agent: str, step_type: str, name: str, *, status: str = "OK", duration_ms: int = 0, input=None,
               output=None, error: str = "", tokens_in: int = 0, tokens_out: int = 0, attempt: int = 1) -> None:
        self.seq += 1
        with session_scope() as db:
            db.add(AgentStep(org_id=self.org_id, run_id=self.run_id, sequence=self.seq, agent=agent, step_type=step_type,
                             name=name, status=status, duration_ms=duration_ms, input=_trim(input or {}),
                             output=_trim(output or {}), error=error[:2000], tokens_in=tokens_in, tokens_out=tokens_out,
                             attempt=attempt))
            run = db.get(AgentRun, self.run_id)
            if run:
                run.step_count = self.seq
                if step_type == "TOOL_CALL":
                    run.tool_call_count += 1
                run.tokens_in += tokens_in
                run.tokens_out += tokens_out


def _trim(obj, limit: int = 6000):
    s = json.dumps(obj, ensure_ascii=False, default=str)
    if len(s) <= limit:
        return json.loads(s)
    return {"_truncated": True, "preview": s[:limit]}


class AgentToolClient:
    """Calls platform tools through MCP (in-process MCPServer or remote streamable HTTP)."""

    def __init__(self, principal: Principal, recorder: StepRecorder, budget: Budget, run_id: str,
                 transport: str = settings.agent_tool_transport, allowed_tools: dict[str, set[str]] | None = None):
        self.principal = principal
        self.recorder = recorder
        self.budget = budget
        self.run_id = run_id
        self.transport = transport
        self.allowed = allowed_tools or {}
        self._stack = AsyncExitStack()
        self._client = None

    async def __aenter__(self):
        from mcp import Client

        if self.transport == "mcp_http":
            import os

            import httpx2
            from mcp.client.streamable_http import streamable_http_client

            key = os.getenv("RIP_AGENT_MCP_API_KEY", "")
            http = await self._stack.enter_async_context(httpx2.AsyncClient(headers={"Authorization": f"Bearer {key}"}, timeout=60))
            transport = streamable_http_client(settings.mcp_url, http_client=http)
            self._client = await self._stack.enter_async_context(Client(transport))
        else:
            from rip_mcp.server import build_server

            server = build_server(default_principal=self.principal, transport_label="mcp_inprocess", run_id=self.run_id)
            self._client = await self._stack.enter_async_context(Client(server))
        return self

    async def __aexit__(self, *exc):
        await self._stack.aclose()

    async def call(self, agent: str, tool: str, args: dict) -> dict:
        # per-agent tool permissions (least privilege inside the workflow)
        if self.allowed and tool not in self.allowed.get(agent, set()):
            self.recorder.record(agent, "TOOL_CALL", tool, status="DENIED", input=args, error="tool not permitted for this agent")
            raise ToolCallFailed(tool, {"code": "TOOL_NOT_PERMITTED", "message": f"{agent} may not call {tool}"})
        self.budget.tool_calls += 1
        self.budget.check()
        t0 = time.perf_counter()
        res = await self._client.call_tool(tool, args)
        dur = int((time.perf_counter() - t0) * 1000)
        payload = res.structured_content
        if payload is None:
            try:
                payload = json.loads(res.content[0].text)
            except Exception:
                detail = " ".join(getattr(c, "text", "") for c in (res.content or []))[:500]
                payload = {"ok": False, "error": {"code": "BAD_TOOL_RESPONSE", "message": f"unparseable tool response: {detail}"}}
        if getattr(res, "is_error", False) or not payload.get("ok", False):
            err = payload.get("error") or {"code": "TOOL_ERROR", "message": str(payload)[:300]}
            self.recorder.record(agent, "TOOL_CALL", tool, status="ERROR", duration_ms=dur, input=args, output=payload,
                                 error=err.get("message", ""))
            raise ToolCallFailed(tool, err, retryable=err.get("code") in ("RATE_LIMITED",))
        self.recorder.record(agent, "TOOL_CALL", tool, duration_ms=dur, input=args, output=payload.get("result", {}))
        return payload["result"]
