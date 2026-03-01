"""
Functional tests for the HTTP server endpoints.

Tests the full ASGI application stack (auth middleware + FastMCP + routing)
using an httpx AsyncClient backed by the ASGI transport.
"""

import pytest
from httpx import AsyncClient


# ── /health ───────────────────────────────────────────────────────────────────


async def test_health_endpoint_returns_200(http_client: AsyncClient) -> None:
    response = await http_client.get("/health")
    assert response.status_code == 200


async def test_health_endpoint_returns_json(http_client: AsyncClient) -> None:
    response = await http_client.get("/health")
    body = response.json()
    assert body["status"] == "healthy"


async def test_health_endpoint_requires_no_auth(http_client: AsyncClient) -> None:
    """Health probe must be reachable without a JWT — ALB needs this."""
    response = await http_client.get("/health")
    assert response.status_code == 200


# ── /mcp — authenticated MCP endpoint ────────────────────────────────────────


async def test_mcp_tools_list_with_valid_token(
    http_client: AsyncClient, valid_token: str
) -> None:
    response = await http_client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 200
    body = response.json()
    assert "result" in body
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "echo" in tool_names
    assert "add" in tool_names


async def test_mcp_tool_call_echo(http_client: AsyncClient, valid_token: str) -> None:
    response = await http_client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"text": "hello from test"}},
        },
    )
    assert response.status_code == 200
    body = response.json()
    content = body["result"]["content"]
    assert any("hello from test" in str(item) for item in content)


async def test_mcp_tool_call_add(http_client: AsyncClient, valid_token: str) -> None:
    response = await http_client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "add", "arguments": {"a": 7, "b": 3}},
        },
    )
    assert response.status_code == 200
    body = response.json()
    content = body["result"]["content"]
    assert any("10" in str(item) for item in content)


async def test_mcp_endpoint_without_token_returns_401(
    http_client: AsyncClient,
) -> None:
    response = await http_client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 401
