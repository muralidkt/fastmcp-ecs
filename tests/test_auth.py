"""
Unit tests for JWT bearer-token authentication.

Tests validate that:
  - Valid tokens are accepted
  - Expired tokens are rejected with HTTP 401
  - Requests with no Authorization header are rejected with HTTP 401
  - Tokens signed with the wrong key are rejected with HTTP 401
"""

from datetime import timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient

from tests.conftest import make_token


async def test_valid_token_reaches_mcp_endpoint(
    http_client: AsyncClient, valid_token: str
) -> None:
    response = await http_client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    # 200 means auth passed; MCP may return 200 with a result or error body
    assert response.status_code == 200


async def test_missing_auth_header_returns_401(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 401


async def test_malformed_bearer_token_returns_401(http_client: AsyncClient) -> None:
    response = await http_client.post(
        "/mcp",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 401


async def test_expired_token_returns_401(
    http_client: AsyncClient, expired_token: str
) -> None:
    response = await http_client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {expired_token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 401


async def test_token_signed_with_wrong_key_returns_401(
    http_client: AsyncClient, test_settings
) -> None:
    # Generate a different key pair — not trusted by the server
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_private_pem = other_private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    bad_token = make_token(
        other_private_pem,
        test_settings.jwt_issuer,
        test_settings.jwt_audience,
    )

    response = await http_client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {bad_token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 401


async def test_wrong_audience_token_returns_401(
    http_client: AsyncClient, rsa_key_pair: dict[str, str], test_settings
) -> None:
    wrong_audience_token = make_token(
        rsa_key_pair["private"],
        test_settings.jwt_issuer,
        "wrong-audience",
    )
    response = await http_client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {wrong_audience_token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert response.status_code == 401
