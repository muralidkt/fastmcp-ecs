# fastmcp-ecs

A production-ready template for deploying a [FastMCP](https://gofastmcp.com) server to AWS ECS Fargate. Includes JWT bearer-token authentication, an Application Load Balancer, CDK infrastructure-as-code, and a full test suite.

## What's included

| Layer | Technology |
|---|---|
| MCP server | [FastMCP](https://gofastmcp.com) + [Uvicorn](https://www.uvicorn.org) |
| Authentication | JWT RS256 bearer tokens via `BearerAuthProvider` |
| Container | Multi-stage Docker build (Python 3.11-slim) |
| Infrastructure | AWS CDK (Python) — VPC, ECS Fargate, ALB, ECR, Secrets Manager |
| Project tooling | [Hatch](https://hatch.pypa.io) — dev, test, lint, deploy |
| Tests | Pytest (functional style) + httpx ASGI transport |

## Prerequisites

- Python 3.11+
- [Hatch](https://hatch.pypa.io/latest/install/) — `pip install hatch`
- [Docker](https://docs.docker.com/get-docker/)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configured with appropriate credentials
- [Node.js](https://nodejs.org/) + AWS CDK CLI — `npm install -g aws-cdk`

## Repository structure

```
src/
  mcp_server/           Python package (installable as `mcp_server`)
    main.py             Uvicorn entry point
    server.py           ASGI app factory — build_app(settings)
    config.py           Pydantic Settings (env-driven)
    auth/
      bearer.py         JWT BearerAuthProvider wiring
    tools/
      example.py        Sample tools + register_tools() helper

IaC/                    AWS CDK infrastructure
  app.py                CDK app entry point
  stacks/
    network_stack.py    VPC, subnets, ALB and ECS security groups
    ecs_stack.py        ECR, ECS cluster, Fargate service, Secrets Manager
  constructs/
    fargate_service.py  Reusable ALB + Fargate construct with auto-scaling

tests/
  conftest.py           Shared fixtures (RSA keys, HTTP client, MCP client)
  test_tools.py         Tool unit tests via in-process FastMCP client
  test_auth.py          JWT auth edge cases (expired, wrong key, missing header)
  test_server.py        Full HTTP endpoint tests (health, tools/list, tools/call)
```

## Quick start

### 1. Clone and install

```bash
git clone <repo-url> my-mcp-server
cd my-mcp-server
pip install hatch
```

### 2. Add your tools

Edit `src/mcp_server/tools/example.py` and register them via `register_tools()`. Replace the package name `mcp_server` with your service name if desired.

### 3. Generate an RSA key pair

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

> **Important:** `private.pem` is used only by the token-issuing service to sign JWTs. Never commit it or deploy it to ECS. `public.pem` goes into AWS Secrets Manager (step 6).

### 4. Run locally

Create a `.env` file (not committed — listed in `.gitignore`):

```
JWT_PUBLIC_KEY=<contents of public.pem>
JWT_ISSUER=my-service
JWT_AUDIENCE=mcp-clients
```

Then start the dev server:

```bash
hatch run dev
```

The server starts at `http://localhost:8000`. The `/health` endpoint requires no auth; all `/mcp` endpoints require a valid JWT.

### 5. Run tests

```bash
hatch run test
```

Tests generate a fresh RSA key pair in-process — no `.env` file needed.

### 6. Deploy infrastructure

Bootstrap CDK once per AWS account/region:

```bash
hatch run iac:bootstrap
```

Deploy all stacks:

```bash
hatch run iac:deploy
```

The deploy output prints values you'll need for the next step:

```
Outputs:
  FastMCPECS.EcrRepositoryUri = <ecr-repo-uri>
  FastMCPECS.EcsClusterName   = FastMCPCluster
  FastMCPECS.EcsServiceName   = <service-name>
  FastMCPECS.AlbDnsName       = <alb-dns-name>
  FastMCPECS.JwtSecretArn     = <secrets-manager-arn>
```

Upload your RSA public key to Secrets Manager:

```bash
aws secretsmanager put-secret-value \
  --secret-id fastmcp-ecs/jwt-public-key \
  --secret-string "$(cat public.pem)"
```

### 7. Build and deploy the container image

Export the stack outputs from step 6, then run the release pipeline:

```bash
export ECR_REPO_URI=<EcrRepositoryUri>
export AWS_REGION=<your-region>
export ECS_CLUSTER=<EcsClusterName>
export ECS_SERVICE=<EcsServiceName>

hatch run docker:release
```

This builds the image, authenticates to ECR, pushes, and forces ECS to redeploy.

## Hatch command reference

### Development

```bash
hatch run test          # run the test suite
hatch run lint          # ruff lint check
hatch run format        # ruff auto-format
hatch run dev           # dev server with auto-reload (requires .env)
```

### Infrastructure (CDK)

```bash
hatch run iac:bootstrap  # one-time CDK bootstrap
hatch run iac:synth      # preview CloudFormation output
hatch run iac:diff       # show pending changes
hatch run iac:deploy     # create or update all stacks
hatch run iac:destroy    # tear down all stacks
```

### Docker & ECS

```bash
hatch run docker:build           # build and tag image for ECR
hatch run docker:push            # build → ECR login → push
hatch run docker:deploy-service  # force ECS to pull new image and restart tasks
hatch run docker:release         # full pipeline: push + redeploy (use for updates)
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `JWT_PUBLIC_KEY` | Yes | — | RSA public key PEM for validating incoming JWTs |
| `JWT_ISSUER` | No | `fastmcp-ecs` | Expected `iss` claim in JWT |
| `JWT_AUDIENCE` | No | `mcp-clients` | Expected `aud` claim in JWT |
| `APP_NAME` | No | `FastMCP Server` | Server name shown in MCP metadata |
| `HOST` | No | `0.0.0.0` | Bind address |
| `PORT` | No | `8000` | Bind port |

In production, `JWT_PUBLIC_KEY` is injected by ECS from AWS Secrets Manager — no manual configuration required after step 6.

## Authentication

This template uses RS256 JWT bearer tokens:

- **Server** holds only the **RSA public key** (in Secrets Manager) to validate tokens.
- **Token issuer** holds the **RSA private key** to sign tokens — this is separate from this service.
- Clients pass tokens in the `Authorization: Bearer <token>` header.
- The `/health` endpoint is exempt from auth for ALB health checks.

## AWS architecture

```
Internet
    │
    ▼
Application Load Balancer (public subnets)
    │  HTTP :80
    ▼
ECS Fargate Tasks (private subnets)
    │  port 8000
    ├── /health        → 200 OK (no auth)
    └── /mcp           → FastMCP (JWT required)
         │
         └── JWT_PUBLIC_KEY ← AWS Secrets Manager
```

Two CDK stacks are deployed in order:

1. **FastMCPNetwork** — VPC (2 AZs, public + private subnets, 1 NAT gateway), ALB security group, ECS security group.
2. **FastMCPECS** — ECR repository, ECS cluster (Container Insights enabled), ALB-fronted Fargate service with CPU auto-scaling and deployment circuit breaker, Secrets Manager secret for the JWT public key.

## Customising this template

- **Add tools:** Add functions to `src/mcp_server/tools/` and register them in `register_tools()`.
- **Rename the package:** Rename `src/mcp_server/` and update the import prefix (`mcp_server.`) and the uvicorn target in `pyproject.toml` and `Dockerfile`.
- **Resize the service:** Adjust `cpu`, `memory_limit_mib`, and `desired_count` in `IaC/stacks/ecs_stack.py`.
- **Enable HTTPS:** Add an ACM certificate and HTTPS listener to the ALB in `IaC/constructs/fargate_service.py`.
- **Multiple AZs / HA NAT:** Increase `nat_gateways=2` in `IaC/stacks/network_stack.py`.
