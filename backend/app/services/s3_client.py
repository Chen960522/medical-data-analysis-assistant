"""S3 client service for file operations.

Provides upload, delete, and presigned URL generation for data files.
"""

import boto3
from botocore.exceptions import ClientError

from ..core.config import settings


def _get_s3_client():
    """Create and return an S3 client configured for the application."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.aws_region,
        aws_access_key_id="test",  # LocalStack default
        aws_secret_access_key="test",  # LocalStack default
    )


def ensure_bucket_exists() -> None:
    """Ensure the S3 bucket exists, creating it if necessary."""
    client = _get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket_name)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket_name)


def upload_file(s3_key: str, file_content: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload a file to S3.

    Args:
        s3_key: The S3 object key.
        file_content: The file content as bytes.
        content_type: The MIME type of the file.

    Returns:
        The S3 key of the uploaded file.

    Raises:
        ClientError: If the upload fails.
    """
    client = _get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=s3_key,
        Body=file_content,
        ContentType=content_type,
    )
    return s3_key


def delete_file(s3_key: str) -> None:
    """Delete a file from S3.

    Args:
        s3_key: The S3 object key to delete.

    Raises:
        ClientError: If the deletion fails.
    """
    client = _get_s3_client()
    client.delete_object(Bucket=settings.s3_bucket_name, Key=s3_key)


def get_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for downloading a file.

    Args:
        s3_key: The S3 object key.
        expires_in: URL expiration time in seconds (default 1 hour).

    Returns:
        A presigned URL string.
    """
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": s3_key},
        ExpiresIn=expires_in,
    )


def get_file_content(s3_key: str) -> bytes:
    """Download file content from S3.

    Args:
        s3_key: The S3 object key.

    Returns:
        The file content as bytes.

    Raises:
        ClientError: If the download fails.
    """
    client = _get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket_name, Key=s3_key)
    return response["Body"].read()
