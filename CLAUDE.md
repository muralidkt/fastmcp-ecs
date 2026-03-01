# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Template for deploying a [FastMCP](https://gofastmcp.com) MCP server to AWS ECS Fargate. The server uses JWT bearer-token authentication and is fronted by an Application Load Balancer.

## Commands

All commands use [hatch](https://hatch.pypa.io/). Install with `pip install hatch`.

### MCP server development
```bash
hatch run test          # run the full test suite
hatch run lint          # ruff lint check
hatch run format        # ruff auto-format
hatch run dev           # start dev server with auto-reload (needs JWT_PUBLIC_KEY set)
                        # runs: uvicorn mcp_server.main:app --reload --port 8000
```

### Infrastructure (CDK)
Prerequisite: Node.js + `npm install -g aws-cdk`
```bash
hatch run iac:bootstrap   # one-time CDK bootstrap per account/region
hatch run iac:synth       # preview CloudFormation templates
hatch run iac:diff        # show pending changes
hatch run iac:deploy      # create or update all AWS stacks
hatch run iac:destroy     # tear down all AWS stacks
```

### Docker image & ECS deployment
Set these env vars first (values printed by `hatch run iac:deploy`):
```bash
export ECR_REPO_URI=<EcrRepositoryUri>
export AWS_REGION=us-east-1
export ECS_CLUSTER=<EcsClusterName>
export ECS_SERVICE=<EcsServiceName>
export IMAGE_TAG=latest   # optional, defaults to "latest"
```
Then:
```bash
hatch run docker:build           # build image tagged for ECR
hatch run docker:push            # build + ECR login + push
hatch run docker:deploy-service  # force ECS to pull new image
hatch run docker:release         # full pipeline: push + redeploy
```

### JWT key pair setup (one-time)
```bash
# Generate RSA key pair
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem

# Upload the public key to the Secrets Manager secret created by CDK
aws secretsmanager put-secret-value \
  --secret-id fastmcp-ecs/jwt-public-key \
  --secret-string "$(cat public.pem)"

# Keep private.pem in your token-issuing service only — never commit it
```

## Architecture

### Repository layout
```
src/
  mcp_server/   FastMCP server Python package (import as `mcp_server`)
    config.py       Pydantic Settings — reads env vars
    server.py       build_app() factory — side-effect free, used in tests
    main.py         Production entry point (uvicorn mcp_server.main:app)
    auth/
      bearer.py     Creates BearerAuthProvider from Settings
    tools/
      example.py    Sample tools + register_tools(mcp) helper

IaC/          AWS CDK (Python)  — run from inside this directory
  app.py          CDK App: instantiates NetworkStack then ECSStack
  cdk.json        CDK config (app: python app.py)
  stacks/
    network_stack.py  VPC (public + private subnets, NAT GW), ALB SG, ECS SG
    ecs_stack.py      ECR image asset, Secrets Manager, ECS cluster, Fargate service
  constructs/
    fargate_service.py  Reusable ALB+Fargate construct with auto-scaling & circuit breaker

tests/        pytest (functional style — no test classes)
  conftest.py     Session-scoped RSA key generation; fixtures for mcp_client, http_client
  test_tools.py   In-process tool tests via FastMCP Client
  test_auth.py    JWT auth edge cases via httpx ASGI transport
  test_server.py  Full HTTP endpoint tests (health, tools/list, tools/call)
```

### Key design decisions

**`src/mcp_server/server.py` vs `src/mcp_server/main.py`** — `server.py` contains `build_app(settings)` with no module-level side effects so it can be safely imported in tests without setting env vars. `main.py` is the uvicorn entry point that calls `build_app(Settings())`.

**Stateless HTTP mode** — `FastMCP(..., stateless_http=True)` is set in `build_app()`. This eliminates server-side session state so ECS can route requests to any Fargate task without sticky sessions.

**Health endpoint** — FastMCP's ASGI app is mounted at `/` inside a Starlette app that also exposes `GET /health`. The ALB health check and ECS `HEALTHCHECK` both target `/health`, which requires no auth.

**Two CDK stacks** — `NetworkStack` outputs `vpc`, `alb_sg`, `ecs_sg` which `ECSStack` consumes. Separating them lets the VPC be reused across multiple services.

**ECR image on first deploy** — `DockerImageAsset` builds and pushes the Docker image during `cdk deploy`. Subsequent image updates use `hatch run docker:release` (faster, no CDK involved).

**JWT auth flow** — `BearerAuthProvider` validates incoming `Authorization: Bearer <token>` headers using the RSA public key from Secrets Manager. The private key lives only in the token-issuing service.

### CDK stack outputs
After `hatch run iac:deploy`, capture the printed outputs:
| Output | Purpose |
|---|---|
| `EcrRepositoryUri` | `ECR_REPO_URI` env var |
| `EcsClusterName` | `ECS_CLUSTER` env var |
| `EcsServiceName` | `ECS_SERVICE` env var |
| `AlbDnsName` | Public URL for the MCP server |
| `JwtSecretArn` | Secrets Manager ARN to update with RSA public key |
