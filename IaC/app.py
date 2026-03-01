#!/usr/bin/env python3
"""
CDK app entry point.

Run from within the IaC/ directory (or via `hatch run iac:<command>`):
  hatch run iac:synth    # preview CloudFormation output
  hatch run iac:deploy   # create / update all stacks
  hatch run iac:destroy  # tear down all stacks

Stacks deployed (in order):
  1. FastMCPNetwork  — VPC, subnets, security groups
  2. FastMCPECS      — ECR image, ECS cluster, Fargate service, ALB
"""

import os

import aws_cdk as cdk

from stacks.ecs_stack import ECSStack
from stacks.network_stack import NetworkStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
)

network = NetworkStack(app, "FastMCPNetwork", env=env)

ECSStack(
    app,
    "FastMCPECS",
    vpc=network.vpc,
    alb_sg=network.alb_sg,
    ecs_sg=network.ecs_sg,
    env=env,
)

app.synth()
