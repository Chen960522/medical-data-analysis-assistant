"""Database Stack - RDS PostgreSQL (Multi-AZ) and ElastiCache Redis.

- RDS: db.r6g.large, Multi-AZ, encrypted with KMS, auto backup
- ElastiCache: cache.r6g.large, cluster mode, encrypted at rest and in transit

Requirements 7.1: AES-256 encryption at rest via KMS
Requirements 7.2: TLS 1.2+ encryption in transit
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_elasticache as elasticache,
    aws_kms as kms,
)
from constructs import Construct


class DatabaseStack(Stack):
    """Defines RDS PostgreSQL (Multi-AZ) and ElastiCache Redis cluster."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        encryption_key: kms.Key,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Security Groups ---

        # RDS Security Group
        self.rds_security_group = ec2.SecurityGroup(
            self,
            "RdsSecurityGroup",
            vpc=vpc,
            description="Security group for RDS PostgreSQL",
            allow_all_outbound=False,
        )

        # ElastiCache Security Group
        self.redis_security_group = ec2.SecurityGroup(
            self,
            "RedisSecurityGroup",
            vpc=vpc,
            description="Security group for ElastiCache Redis",
            allow_all_outbound=False,
        )

        # Allow inbound from private app subnets
        for subnet in vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        ).subnets:
            self.rds_security_group.add_ingress_rule(
                peer=ec2.Peer.ipv4(subnet.ipv4_cidr_block),
                connection=ec2.Port.tcp(5432),
                description="Allow PostgreSQL from app subnets",
            )
            self.redis_security_group.add_ingress_rule(
                peer=ec2.Peer.ipv4(subnet.ipv4_cidr_block),
                connection=ec2.Port.tcp(6379),
                description="Allow Redis from app subnets",
            )

        # --- RDS PostgreSQL (Multi-AZ) ---

        # Subnet group for RDS in private data subnets
        self.db_instance = rds.DatabaseInstance(
            self,
            "MedicalAnalysisDb",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.R6G, ec2.InstanceSize.LARGE
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[self.rds_security_group],
            multi_az=True,
            database_name="medical_analysis",
            credentials=rds.Credentials.from_generated_secret("dbadmin"),
            storage_encrypted=True,
            storage_encryption_key=encryption_key,
            backup_retention=Duration.days(7),
            deletion_protection=True,
            removal_policy=RemovalPolicy.RETAIN,
            auto_minor_version_upgrade=True,
            allocated_storage=100,
            max_allocated_storage=500,
        )

        # --- ElastiCache Redis Cluster ---

        # Subnet group for Redis in private data subnets
        redis_subnet_group = elasticache.CfnSubnetGroup(
            self,
            "RedisSubnetGroup",
            description="Subnet group for ElastiCache Redis",
            subnet_ids=[
                subnet.subnet_id
                for subnet in vpc.select_subnets(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
                ).subnets
            ],
        )

        # Redis replication group with encryption
        self.redis_cluster = elasticache.CfnReplicationGroup(
            self,
            "MedicalAnalysisRedis",
            replication_group_description="Medical Analysis Redis cluster",
            engine="redis",
            cache_node_type="cache.r6g.large",
            num_cache_clusters=2,
            automatic_failover_enabled=True,
            multi_az_enabled=True,
            cache_subnet_group_name=redis_subnet_group.ref,
            security_group_ids=[self.redis_security_group.security_group_id],
            # Encryption at rest (Req 7.1)
            at_rest_encryption_enabled=True,
            kms_key_id=encryption_key.key_id,
            # Encryption in transit (Req 7.2 - TLS)
            transit_encryption_enabled=True,
            engine_version="7.0",
            port=6379,
        )
