import os

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from constructs.fargate_service import AlbFargateService


class ECSStack(cdk.Stack):
    """
    ECS Fargate stack for the FastMCP server.

    Resources created:
      • ECR image asset (Docker build + push happens during `cdk deploy`)
      • Secrets Manager secret — stores the RSA public key for JWT validation
      • ECS Cluster with Container Insights enabled
      • ALB + Fargate service via AlbFargateService construct
      • CfnOutputs — ECR URI, cluster name, service name, ALB DNS
        (copy these into your shell before running `hatch run docker:release`)
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.Vpc,
        alb_sg: ec2.SecurityGroup,
        ecs_sg: ec2.SecurityGroup,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Docker image ──────────────────────────────────────────────────
        # Build context is the project root (one level above IaC/stacks/).
        project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))

        image_asset = ecr_assets.DockerImageAsset(
            self,
            "McpImage",
            directory=project_root,
            # Exclude IaC and test dirs from the build context
            exclude=["IaC", "tests", ".git", "cdk.out"],
        )

        # ── JWT public key secret ─────────────────────────────────────────
        # After deploying, update the secret value with your RSA public key:
        #   aws secretsmanager put-secret-value \
        #     --secret-id fastmcp-ecs/jwt-public-key \
        #     --secret-string "$(cat public.pem)"
        jwt_secret = secretsmanager.Secret(
            self,
            "JwtPublicKey",
            secret_name="fastmcp-ecs/jwt-public-key",
            description="RSA public key (PEM) for FastMCP JWT bearer-token validation",
            # Placeholder — update before the first deployment receives traffic
            string_value="REPLACE_WITH_YOUR_RSA_PUBLIC_KEY_PEM",
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # ── ECS Cluster ───────────────────────────────────────────────────
        cluster = ecs.Cluster(
            self,
            "Cluster",
            cluster_name="FastMCPCluster",
            vpc=vpc,
            container_insights=True,
        )

        # ── Fargate service ───────────────────────────────────────────────
        fargate = AlbFargateService(
            self,
            "FastMCPService",
            cluster=cluster,
            image=ecs.ContainerImage.from_docker_image_asset(image_asset),
            environment={
                "APP_NAME": "FastMCP Server",
                "JWT_ISSUER": "fastmcp-ecs",
                "JWT_AUDIENCE": "mcp-clients",
                "PORT": "8000",
            },
            secrets={
                # Injected as JWT_PUBLIC_KEY env var inside the container
                "JWT_PUBLIC_KEY": ecs.Secret.from_secrets_manager(jwt_secret),
            },
            container_port=8000,
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            health_check_path="/health",
        )

        # Allow the ALB to reach ECS tasks
        fargate.load_balancer.connections.add_security_group(alb_sg)
        fargate.fargate_service.connections.add_security_group(ecs_sg)

        # ── Stack outputs ─────────────────────────────────────────────────
        # Export these values as env vars before running `hatch run docker:release`:
        #   export ECR_REPO_URI=<EcrRepositoryUri>
        #   export ECS_CLUSTER=<EcsClusterName>
        #   export ECS_SERVICE=<EcsServiceName>
        cdk.CfnOutput(
            self,
            "EcrRepositoryUri",
            value=image_asset.repository.repository_uri,
            description="Set as ECR_REPO_URI for `hatch run docker:release`",
        )
        cdk.CfnOutput(
            self,
            "EcsClusterName",
            value=cluster.cluster_name,
            description="Set as ECS_CLUSTER for `hatch run docker:deploy-service`",
        )
        cdk.CfnOutput(
            self,
            "EcsServiceName",
            value=fargate.fargate_service.service_name,
            description="Set as ECS_SERVICE for `hatch run docker:deploy-service`",
        )
        cdk.CfnOutput(
            self,
            "AlbDnsName",
            value=fargate.load_balancer.load_balancer_dns_name,
            description="Public DNS name of the Application Load Balancer",
        )
        cdk.CfnOutput(
            self,
            "JwtSecretArn",
            value=jwt_secret.secret_arn,
            description="Secrets Manager ARN — update with your RSA public key PEM",
        )
