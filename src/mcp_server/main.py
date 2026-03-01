"""
Production entry point — creates the module-level `app` used by uvicorn.

    uvicorn mcp_server.main:app --host 0.0.0.0 --port 8000

JWT_PUBLIC_KEY (and optionally JWT_ISSUER, JWT_AUDIENCE) must be set in the
environment before starting the server.  In ECS these are injected from
AWS Secrets Manager / Secrets configuration on the task definition.
"""

import uvicorn

from mcp_server.config import Settings
from mcp_server.server import build_app

settings = Settings()
app = build_app(settings)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
