"""
ASGI application factory.

Importing this module has no side-effects, making it safe to use in tests
without needing environment variables set at import time.
"""

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp_server.auth.bearer import create_auth_provider
from mcp_server.config import Settings
from mcp_server.tools.example import register_tools


async def health_check(request: Request) -> JSONResponse:
    """Liveness probe endpoint — used by ALB and ECS health checks."""
    return JSONResponse({"status": "healthy"})


def build_app(settings: Settings) -> Starlette:
    """
    Build and return the full ASGI application.

    Architecture:
      GET  /health  →  liveness probe (no auth required)
      *    /        →  FastMCP ASGI app (JWT bearer auth enforced)

    For ECS deployments behind an ALB, FastMCP runs in stateless HTTP mode
    so that any task can serve any request without sticky sessions.
    """
    auth = create_auth_provider(settings)

    # stateless_http=True is required for load-balanced multi-task ECS deployments.
    # It disables server-side session state so requests can hit any Fargate task.
    mcp = FastMCP(settings.app_name, auth=auth, stateless_http=True)
    register_tools(mcp)

    mcp_asgi = mcp.http_app()

    return Starlette(
        routes=[
            Route("/health", health_check),
            Mount("/", mcp_asgi),
        ]
    )
