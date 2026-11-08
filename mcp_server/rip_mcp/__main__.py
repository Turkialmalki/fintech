from __future__ import annotations

import argparse
import logging

import uvicorn
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.config import settings
from rip_mcp.server import build_server


def main() -> None:
    ap = argparse.ArgumentParser(description="RIP MCP server")
    ap.add_argument("--transport", choices=["stdio", "streamable-http"], default="streamable-http")
    ap.add_argument("--host", default=settings.mcp_host)
    ap.add_argument("--port", type=int, default=settings.mcp_port)
    a = ap.parse_args()
    logging.basicConfig(level=settings.log_level)
    server = build_server(transport_label=f"mcp_{a.transport.replace('-', '_')}")
    if a.transport == "stdio":
        server.run("stdio")
        return
    app = server.streamable_http_app(stateless_http=True, json_response=True, host=a.host)

    async def health(_: Request):
        return JSONResponse({"status": "ok", "service": "rip-mcp", "tools": 10})

    app.router.routes.append(Route("/healthz", health))
    uvicorn.run(app, host=a.host, port=a.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
