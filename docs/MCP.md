# MCP server (`backend/rip_mcp`)

Built on the official Python MCP SDK (`mcp==2.3.0`, `mcp.server.mcpserver.MCPServer`). It exposes **controlled**
application capabilities — each tool maps to a deterministic service with a Pydantic input model, a required permission
and a read/write flag (`backend/app/services/tools.py`). There is no generic SQL, file-system or network access.

| Tool | Access | Permission |
|---|---|---|
| `search_regulations` | read | regulatory:read |
| `get_regulation_details` | read | regulatory:read |
| `get_fintech_application` | read | applications:read |
| `list_application_documents` | read | applications:read |
| `check_required_documents` | read | applications:read |
| `analyze_application` | read | assessments:read |
| `get_risk_indicators` | read | assessments:read |
| `create_assessment_draft` | **write** | assessments:run + key scope `write` |
| `get_assessment_history` | read | assessments:read |
| `submit_for_human_review` | **write** | assessments:run + key scope `write` (does not approve anything) |

## Run
```bash
cd backend && PYTHONPATH=. python -m rip_mcp --transport streamable-http --port 8765   # http://host:8765/mcp, /healthz
PYTHONPATH=. RIP_MCP_API_KEY=rip_... python -m rip_mcp --transport stdio
docker compose up mcp
```

## Authentication & authorisation
1. Create a key in **أدوات الربط والتكامل → مفاتيح الوصول** (or `POST /api/v1/mcp/keys`). Only the SHA-256 hash is stored; the key is shown once.
2. Send `Authorization: Bearer rip_...` (HTTP) or set `RIP_MCP_API_KEY` (stdio).
3. The key acts as its owner's user with the owner's permissions and tenant, `actor_type=MCP_CLIENT`, and the key's scopes.
   Keys are read-only unless created with **السماح بأدوات الكتابة**. Revocation is immediate.
4. Every call is rate limited (`MCP_RATE_LIMIT_PER_MINUTE`) and audited (`category=MCP`, tool, transport, duration,
   arguments with redaction, outcome). Errors are returned as structured results: `{"ok": false, "error": {code, message, message_ar}}`.

## Client configuration examples
```json
{ "mcpServers": { "rip": { "url": "https://mcp.rip.example.com/mcp", "headers": { "Authorization": "Bearer rip_..." } } } }
```
```json
{ "mcpServers": { "rip": { "command": "python", "args": ["-m", "rip_mcp", "--transport", "stdio"],
  "env": { "RIP_MCP_API_KEY": "rip_...", "DATABASE_URL": "postgresql+psycopg://...", "PYTHONPATH": "/path/backend" } } } }
```

Python client:
```python
import asyncio, httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer rip_..."}) as http:
        async with Client(streamable_http_client("http://localhost:8765/mcp", http_client=http)) as c:
            print(await c.call_tool("search_regulations", {"query": "متطلبات رأس المال", "top_k": 3}))
asyncio.run(main())
```

## How the agents use it
The LangGraph agents open an MCP session for each run: in-process (`AGENT_TOOL_TRANSPORT=mcp_inprocess`, default) or against
the standalone server (`mcp_http`, using `RIP_AGENT_MCP_API_KEY` with the write scope). Both paths were verified: the
remote-HTTP run made 25 tool calls, all audited with `transport=mcp_streamable_http`.
