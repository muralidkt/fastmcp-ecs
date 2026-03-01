"""
Shared pytest fixtures.

Fixtures are function-scoped by default unless explicitly set to "session".
RSA key generation is session-scoped (expensive) — everything else is function-scoped
so tests remain fully isolated.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastmcp import Client, FastMCP
from httpx import ASGITransport, AsyncClient

from mcp_server.config import Settings
from mcp_server.server import build_app
from mcp_server.tools.example import register_tools


# ── RSA key pair ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def rsa_key_pair() -> dict[str, str]:
    """Generate a fresh RSA-2048 key pair for the test session."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {
        "private": private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        "public": private_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
    }


# ── Settings & app ────────────────────────────────────────────────────────────


@pytest.fixture
def test_settings(rsa_key_pair: dict[str, str]) -> Settings:
    """Settings instance wired to the test RSA public key."""
    return Settings(
        jwt_public_key=rsa_key_pair["public"],
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
    )


@pytest.fixture
def authed_app(test_settings: Settings):  # type: ignore[return]
    """Full ASGI application with JWT auth enabled — for HTTP integration tests."""
    return build_app(test_settings)


# ── JWT token helpers ─────────────────────────────────────────────────────────


def make_token(
    private_key: str,
    issuer: str,
    audience: str,
    *,
    expires_in: timedelta = timedelta(hours=1),
    **extra_claims: object,
) -> str:
    """Create a signed RS256 JWT for use in tests."""
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "sub": "test-client",
        "iss": issuer,
        "aud": [audience],
        "iat": now,
        "exp": now + expires_in,
        **extra_claims,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.fixture
def valid_token(rsa_key_pair: dict[str, str], test_settings: Settings) -> str:
    """A valid, non-expired JWT signed with the test private key."""
    return make_token(
        rsa_key_pair["private"],
        test_settings.jwt_issuer,
        test_settings.jwt_audience,
    )


@pytest.fixture
def expired_token(rsa_key_pair: dict[str, str], test_settings: Settings) -> str:
    """An expired JWT — should be rejected by the auth provider."""
    return make_token(
        rsa_key_pair["private"],
        test_settings.jwt_issuer,
        test_settings.jwt_audience,
        expires_in=timedelta(seconds=-1),
    )


# ── FastMCP in-process client ─────────────────────────────────────────────────


@pytest.fixture
def plain_mcp() -> FastMCP:
    """A FastMCP instance without auth — suitable for unit-testing tools."""
    server = FastMCP("TestServer")
    register_tools(server)
    return server


@pytest.fixture
async def mcp_client(plain_mcp: FastMCP) -> AsyncClient:  # type: ignore[return]
    """In-process FastMCP client — no HTTP overhead, no auth required."""
    async with Client(plain_mcp) as client:
        yield client  # type: ignore[misc]


# ── HTTPX ASGI client ─────────────────────────────────────────────────────────


@pytest.fixture
async def http_client(authed_app):  # type: ignore[return]
    """httpx AsyncClient backed by the ASGI app — for HTTP-level tests."""
    async with AsyncClient(
        transport=ASGITransport(app=authed_app),
        base_url="http://testserver",
    ) as client:
        yield client  # type: ignore[misc]
