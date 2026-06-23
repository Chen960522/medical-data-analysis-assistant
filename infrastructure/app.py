#!/usr/bin/env python3
"""CDK App entry point for Medical Data Analysis Assistant infrastructure.

Instantiates all stacks with proper dependency ordering:
1. NetworkStack - VPC, subnets, VPC Endpoints
2. SecurityStack - KMS encryption key
3. DatabaseStack - RDS PostgreSQL, ElastiCache Redis (depends on Network, Security)
4. StorageStack - S3 buckets (depends on Security)
5. ComputeStack - ECS Fargate, ALB (depends on Network, Security)
6. CdnStack - CloudFront distribution (depends on Storage)
"""

import aws_cdk as cdk

from stacks.network_stack import NetworkStack
from stacks.security_stack import SecurityStack
from stacks.database_stack import DatabaseStack
from stacks.storage_stack import StorageStack
from stacks.compute_stack import ComputeStack
from stacks.cdn_stack import CdnStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or "us-west-2",
)

# 1. Network Stack - VPC with 3 subnet tiers and VPC Endpoints
network_stack = NetworkStack(app, "MedicalAnalysis-Network", env=env)

# 2. Security Stack - KMS encryption key
security_stack = SecurityStack(app, "MedicalAnalysis-Security", env=env)

# 3. Database Stack - RDS PostgreSQL (Multi-AZ) + ElastiCache Redis
database_stack = DatabaseStack(
    app,
    "MedicalAnalysis-Database",
    vpc=network_stack.vpc,
    encryption_key=security_stack.encryption_key,
    env=env,
)
database_stack.add_dependency(network_stack)
database_stack.add_dependency(security_stack)

# 4. Storage Stack - S3 buckets (data, reports, frontend)
storage_stack = StorageStack(
    app,
    "MedicalAnalysis-Storage",
    encryption_key=security_stack.encryption_key,
    env=env,
)
storage_stack.add_dependency(security_stack)

# 5. Compute Stack - ECS Fargate cluster, ALB, API + MCP services
compute_stack = ComputeStack(
    app,
    "MedicalAnalysis-Compute",
    vpc=network_stack.vpc,
    encryption_key=security_stack.encryption_key,
    db_instance=database_stack.db_instance,
    redis_cluster=database_stack.redis_cluster,
    data_bucket=storage_stack.data_bucket,
    reports_bucket=storage_stack.reports_bucket,
    jwt_secret=security_stack.jwt_secret,
    env=env,
)
compute_stack.add_dependency(network_stack)
compute_stack.add_dependency(security_stack)
compute_stack.add_dependency(database_stack)
compute_stack.add_dependency(storage_stack)

# 6. CDN Stack - CloudFront + S3 origin for frontend
cdn_stack = CdnStack(
    app,
    "MedicalAnalysis-Cdn",
    alb=compute_stack.alb,
    env=env,
)
cdn_stack.add_dependency(compute_stack)

app.synth()
