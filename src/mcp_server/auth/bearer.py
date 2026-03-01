from fastmcp.server.auth import BearerAuthProvider

from mcp_server.config import Settings


def create_auth_provider(settings: Settings) -> BearerAuthProvider:
    """
    Build a FastMCP BearerAuthProvider from application settings.

    The provider validates JWT bearer tokens using the configured RSA public key.
    Tokens must be signed with the corresponding RSA private key (kept only in
    the token-issuing service — never deployed here).
    """
    return BearerAuthProvider(
        public_key=settings.jwt_public_key,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )
