"""Storage Stack - S3 buckets for data files and reports.

Two buckets:
- Data files: uploaded medical data (CSV, Excel, JSON, PDF)
- Reports: generated analysis reports (PDF, Word)

Note: Frontend static assets bucket is in CdnStack to avoid cross-stack cycles.

Requirements 7.1: AES-256 encryption at rest via KMS
Requirements 7.2: TLS enforced via bucket policy (deny non-SSL requests)
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
    aws_kms as kms,
)
from constructs import Construct


class StorageStack(Stack):
    """Defines S3 buckets with KMS encryption and lifecycle policies."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        encryption_key: kms.Key,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Data Files Bucket ---
        self.data_bucket = s3.Bucket(
            self,
            "DataFilesBucket",
            encryption=s3.BucketEncryption.KMS,
            encryption_key=encryption_key,
            enforce_ssl=True,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90),
                        )
                    ],
                ),
            ],
        )

        # --- Reports Bucket ---
        self.reports_bucket = s3.Bucket(
            self,
            "ReportsBucket",
            encryption=s3.BucketEncryption.KMS,
            encryption_key=encryption_key,
            enforce_ssl=True,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ExpireOldReports",
                    expiration=Duration.days(365),
                ),
            ],
        )
