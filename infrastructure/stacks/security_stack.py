"""Security Stack - KMS encryption key for data at rest + JWT signing secret.

Requirements 7.1: Encrypt all uploaded Medical_Data at rest using AES-256 encryption.
Requirements 7.2: Encrypt all data in transit using TLS 1.2 or higher.

KMS provides AES-256 encryption for S3, RDS, and ElastiCache.
TLS is enforced at the service level (ALB, CloudFront, RDS, ElastiCache).
The JWT signing secret is generated and stored in Secrets Manager and injected
into the API ECS task as a secret (never a plaintext environment variable).
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_kms as kms,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class SecurityStack(Stack):
    """Defines KMS encryption keys for data at rest (AES-256)."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Master encryption key for all data at rest
        self.encryption_key = kms.Key(
            self,
            "MedicalDataEncryptionKey",
            alias="medical-analysis/data-encryption",
            description="KMS key for encrypting medical data at rest (AES-256)",
            enable_key_rotation=True,
            pending_window=Duration.days(30),
            removal_policy=RemovalPolicy.RETAIN,
        )

        # JWT signing secret (APP_JWT_SECRET_KEY). A random 64-char string is
        # generated and stored in Secrets Manager; the ECS task injects it as a
        # secret so the signing key is never a plaintext environment variable.
        self.jwt_secret = secretsmanager.Secret(
            self,
            "JwtSigningSecret",
            description="JWT signing key for the medical analysis API",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=64,
                exclude_punctuation=True,
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )
