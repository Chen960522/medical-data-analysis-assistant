"""Compute Stack - ECS Fargate cluster, ALB, API service, and MCP Servers service.

- ECS Fargate cluster for containerized services
- ALB in public subnets with HTTPS (TLS 1.2+)
- API Service: 2 vCPU / 4GB RAM, auto-scaling 2-10 instances
- MCP Servers Service: independent tasks, on-demand scaling

Requirements 7.2: TLS 1.2+ encryption in transit (ALB HTTPS listener)

Container images are built from the repository Dockerfiles and pushed to ECR
automatically via CDK assets (``ecs.ContainerImage.from_asset``):
- API service:  ../backend/Dockerfile
- MCP service:  ../mcp-servers/Dockerfile
"""

from pathlib import Path

from aws_cdk import (
    Stack,
    Duration,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    aws_kms as kms,
    aws_iam as iam,
    aws_rds as rds,
    aws_elasticache as elasticache,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

# Repository root relative to this file: infrastructure/stacks/ -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = str(_REPO_ROOT / "backend")
_MCP_DIR = str(_REPO_ROOT / "mcp-servers")


class ComputeStack(Stack):
    """Defines ECS Fargate cluster, ALB, API service, and MCP Servers."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        encryption_key: kms.Key,
        db_instance: rds.DatabaseInstance,
        redis_cluster: elasticache.CfnReplicationGroup,
        data_bucket: s3.Bucket,
        reports_bucket: s3.Bucket,
        jwt_secret: secretsmanager.Secret,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Region used for AWS SDK calls and Bedrock (overridable via context).
        bedrock_region = self.node.try_get_context("bedrock_region") or "us-west-2"
        agentcore_region = self.node.try_get_context("agentcore_region") or bedrock_region
        # ARN of the deployed AgentCore Runtime (optional at synth; required at
        # runtime for the Agent to function). Provide via:
        #   cdk deploy -c agentcore_runtime_arn=arn:aws:bedrock-agentcore:...
        agentcore_runtime_arn = self.node.try_get_context("agentcore_runtime_arn") or ""

        # Redis connection string. transit_encryption is enabled on the cluster
        # (DatabaseStack), so use the TLS scheme ``rediss://``.
        redis_endpoint = redis_cluster.attr_primary_end_point_address
        redis_port = redis_cluster.attr_primary_end_point_port
        redis_url = f"rediss://{redis_endpoint}:{redis_port}/0"

        # Plain environment for the API container. Secrets (DB user/password,
        # JWT key) are injected separately via ``secrets`` below so they never
        # appear as plaintext in the task definition.
        api_environment = {
            "ENV": "production",
            "PORT": "8000",
            # Database parts (password/user injected as secrets). config.py
            # assembles APP_DATABASE_URL from these when APP_DB_HOST is set.
            "APP_DB_HOST": db_instance.db_instance_endpoint_address,
            "APP_DB_PORT": db_instance.db_instance_endpoint_port,
            "APP_DB_NAME": "medical_analysis",
            # Redis / cache
            "APP_REDIS_URL": redis_url,
            # S3 (empty endpoint => real AWS S3, not LocalStack)
            "APP_S3_BUCKET_NAME": data_bucket.bucket_name,
            "APP_S3_ENDPOINT_URL": "",
            "APP_AWS_REGION": self.region,
            # Bedrock / AgentCore
            "APP_BEDROCK_REGION": bedrock_region,
            "APP_AGENTCORE_REGION": agentcore_region,
            "APP_AGENTCORE_RUNTIME_ARN": agentcore_runtime_arn,
        }

        # Secrets injected from Secrets Manager (ECS execution role is granted
        # read automatically by ecs.Secret).
        api_secrets = {
            "APP_DB_USER": ecs.Secret.from_secrets_manager(db_instance.secret, "username"),
            "APP_DB_PASSWORD": ecs.Secret.from_secrets_manager(db_instance.secret, "password"),
            "APP_JWT_SECRET_KEY": ecs.Secret.from_secrets_manager(jwt_secret),
        }

        # --- ECS Cluster ---
        self.cluster = ecs.Cluster(
            self,
            "MedicalAnalysisCluster",
            vpc=vpc,
            container_insights=True,
        )

        # --- Application Load Balancer ---
        self.alb = elbv2.ApplicationLoadBalancer(
            self,
            "MedicalAnalysisAlb",
            vpc=vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            ),
        )

        # HTTP listener - redirect to HTTPS
        self.alb.add_listener(
            "HttpListener",
            port=80,
            default_action=elbv2.ListenerAction.redirect(
                protocol="HTTPS",
                port="443",
                permanent=True,
            ),
        )

        # HTTPS listener (TLS 1.2+ per Req 7.2)
        # Certificate ARN must be provided via CDK context at deploy time:
        #   cdk deploy -c certificate_arn=arn:aws:acm:...
        certificate_arn = self.node.try_get_context("certificate_arn")
        if certificate_arn:
            certificate = elbv2.ListenerCertificate.from_arn(certificate_arn)
        else:
            # For synth/testing without a real certificate, use a placeholder
            certificate = None

        if certificate:
            self.https_listener = self.alb.add_listener(
                "HttpsListener",
                port=443,
                protocol=elbv2.ApplicationProtocol.HTTPS,
                certificates=[certificate],
                ssl_policy=elbv2.SslPolicy.TLS12,
                default_action=elbv2.ListenerAction.fixed_response(
                    status_code=404,
                    content_type="application/json",
                    message_body='{"error": "Not Found"}',
                ),
            )
        else:
            # Fallback: HTTP listener for local dev/synth (HTTPS required in prod)
            self.https_listener = self.alb.add_listener(
                "HttpsListener",
                port=443,
                protocol=elbv2.ApplicationProtocol.HTTP,
                default_action=elbv2.ListenerAction.fixed_response(
                    status_code=404,
                    content_type="application/json",
                    message_body='{"error": "Not Found"}',
                ),
            )

        # --- API Service (FastAPI) ---

        # Task definition: 2 vCPU / 4GB RAM
        api_task_definition = ecs.FargateTaskDefinition(
            self,
            "ApiTaskDef",
            cpu=2048,
            memory_limit_mib=4096,
        )

        api_task_definition.add_container(
            "ApiContainer",
            image=ecs.ContainerImage.from_asset(_BACKEND_DIR),
            port_mappings=[
                ecs.PortMapping(container_port=8000, protocol=ecs.Protocol.TCP)
            ],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="api",
                log_retention=logs.RetentionDays.ONE_MONTH,
            ),
            environment=api_environment,
            secrets=api_secrets,
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
            ),
        )

        # API Fargate Service
        self.api_service = ecs.FargateService(
            self,
            "ApiService",
            cluster=self.cluster,
            task_definition=api_task_definition,
            desired_count=2,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            assign_public_ip=False,
        )

        # Auto-scaling: 2-10 instances
        api_scaling = self.api_service.auto_scale_task_count(
            min_capacity=2,
            max_capacity=10,
        )
        api_scaling.scale_on_cpu_utilization(
            "ApiCpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        # Register API service with ALB target group
        api_target_group = elbv2.ApplicationTargetGroup(
            self,
            "ApiTargetGroup",
            vpc=vpc,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[self.api_service],
            health_check=elbv2.HealthCheck(
                path="/health",
                healthy_http_codes="200",
                interval=Duration.seconds(30),
            ),
        )

        self.https_listener.add_target_groups(
            "ApiTargetRule",
            priority=10,
            conditions=[
                elbv2.ListenerCondition.path_patterns(["/api/*"]),
            ],
            target_groups=[api_target_group],
        )

        # --- MCP Servers Service ---

        mcp_task_definition = ecs.FargateTaskDefinition(
            self,
            "McpTaskDef",
            cpu=1024,
            memory_limit_mib=2048,
        )

        mcp_task_definition.add_container(
            "McpContainer",
            image=ecs.ContainerImage.from_asset(_MCP_DIR),
            port_mappings=[
                ecs.PortMapping(container_port=9000, protocol=ecs.Protocol.TCP)
            ],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="mcp-servers",
                log_retention=logs.RetentionDays.ONE_MONTH,
            ),
            environment={
                "ENV": "production",
                "PORT": "9000",
                "APP_S3_BUCKET_NAME": data_bucket.bucket_name,
                "APP_AWS_REGION": self.region,
                "APP_BEDROCK_REGION": bedrock_region,
            },
            secrets={
                "APP_DB_USER": ecs.Secret.from_secrets_manager(db_instance.secret, "username"),
                "APP_DB_PASSWORD": ecs.Secret.from_secrets_manager(db_instance.secret, "password"),
            },
        )

        self.mcp_service = ecs.FargateService(
            self,
            "McpService",
            cluster=self.cluster,
            task_definition=mcp_task_definition,
            desired_count=2,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            assign_public_ip=False,
        )

        # Auto-scaling for MCP Servers
        mcp_scaling = self.mcp_service.auto_scale_task_count(
            min_capacity=2,
            max_capacity=6,
        )
        mcp_scaling.scale_on_cpu_utilization(
            "McpCpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        # --- IAM grants for the task roles ---------------------------------
        # Both the API and MCP services need S3 (data/reports), KMS (to use the
        # encrypted buckets), and Bedrock (model invocation + AgentCore).
        task_roles = [
            api_task_definition.task_role,
            mcp_task_definition.task_role,
        ]

        for role in task_roles:
            # S3 object access on the data and reports buckets.
            data_bucket.grant_read_write(role)
            reports_bucket.grant_read_write(role)
            # KMS for the SSE-KMS encrypted buckets / data.
            encryption_key.grant_encrypt_decrypt(role)

        # Bedrock model invocation + AgentCore runtime invocation.
        bedrock_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock-agentcore:InvokeAgentRuntime",
            ],
            resources=["*"],
        )
        for role in task_roles:
            role.add_to_principal_policy(bedrock_statement)

        # --- Network: allow the ECS tasks to reach RDS and Redis -----------
        # The database/redis security groups (DatabaseStack) currently allow
        # ingress from the private-app subnet CIDRs. The Fargate services run in
        # those subnets, so connectivity is already permitted; no extra ingress
        # rule is added here to avoid a cross-stack security-group cycle.
