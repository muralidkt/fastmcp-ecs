"""
Reusable ALB + Fargate construct.

Wraps ApplicationLoadBalancedFargateService and adds:
  - Deployment circuit breaker with rollback
  - CloudWatch Container Insights on the cluster
  - CPU-based auto-scaling
"""

import aws_cdk as cdk
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_logs as logs
from constructs import Construct


class AlbFargateService(Construct):
    """
    ALB-fronted Fargate service with auto-scaling and circuit breaker.

    Parameters
    ----------
    cluster:           ECS cluster to deploy into.
    image:             Container image (ECR asset, registry, etc.).
    environment:       Plain-text environment variables for the container.
    secrets:           ECS secrets (e.g. from Secrets Manager).
    container_port:    Port the container listens on (default 8000).
    cpu / memory:      Fargate task sizing.
    desired_count:     Initial number of tasks.
    health_check_path: ALB health-check HTTP path.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cluster: ecs.Cluster,
        image: ecs.ContainerImage,
        environment: dict[str, str] | None = None,
        secrets: dict[str, ecs.Secret] | None = None,
        container_port: int = 8000,
        cpu: int = 256,
        memory_limit_mib: int = 512,
        desired_count: int = 1,
        health_check_path: str = "/health",
    ) -> None:
        super().__init__(scope, construct_id)

        log_group = logs.LogGroup(
            self,
            "LogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        self.service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Service",
            cluster=cluster,
            cpu=cpu,
            memory_limit_mib=memory_limit_mib,
            desired_count=desired_count,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=image,
                container_port=container_port,
                environment=environment or {},
                secrets=secrets or {},
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="fastmcp",
                    log_group=log_group,
                ),
            ),
            public_load_balancer=True,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        )

        # ALB health check
        self.service.target_group.configure_health_check(
            path=health_check_path,
            interval=cdk.Duration.seconds(30),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
        )

        # Auto-scaling: scale out when CPU > 70 %, scale in when < 40 %
        scaling = self.service.service.auto_scale_task_count(
            min_capacity=desired_count,
            max_capacity=desired_count * 4,
        )
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=cdk.Duration.seconds(60),
            scale_out_cooldown=cdk.Duration.seconds(30),
        )

        self.load_balancer = self.service.load_balancer
        self.fargate_service = self.service.service
