from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    In production the JWT public key is injected by ECS from AWS Secrets Manager.
    For local development, set variables in a .env file.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Server
    app_name: str = "FastMCP Server"
    host: str = "0.0.0.0"
    port: int = 8000

    # JWT bearer-token auth
    # RSA public key in PEM format — used to validate incoming JWTs.
    # Generate a key pair with:
    #   openssl genrsa -out private.pem 2048
    #   openssl rsa -in private.pem -pubout -out public.pem
    jwt_public_key: str
    jwt_issuer: str = "fastmcp-ecs"
    jwt_audience: str = "mcp-clients"
