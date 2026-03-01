import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkStack(cdk.Stack):
    """
    VPC and security-group layer.

    Topology:
      • 2 AZs
      • Public subnets  → ALB (internet-facing)
      • Private subnets → ECS Fargate tasks (no public IPs)
      • 1 NAT Gateway   → outbound internet access from private subnets

    Security groups:
      alb_sg   — allows HTTP (80) inbound from the internet
      ecs_sg   — allows port 8000 inbound from the ALB only
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "VPC",
            max_azs=2,
            nat_gateways=1,  # increase to 2 for full HA in production
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # ALB security group — internet-facing HTTP
        self.alb_sg = ec2.SecurityGroup(
            self,
            "AlbSecurityGroup",
            vpc=self.vpc,
            description="ALB: allow HTTP from internet",
            allow_all_outbound=True,
        )
        self.alb_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            "Allow HTTP from internet",
        )

        # ECS task security group — only reachable from the ALB
        self.ecs_sg = ec2.SecurityGroup(
            self,
            "ECSSecurityGroup",
            vpc=self.vpc,
            description="ECS tasks: allow port 8000 from ALB only",
            allow_all_outbound=True,
        )
        self.ecs_sg.add_ingress_rule(
            self.alb_sg,
            ec2.Port.tcp(8000),
            "Allow traffic from ALB on container port",
        )

        # Outputs for cross-stack reference visibility in the console
        cdk.CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
