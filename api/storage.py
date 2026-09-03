"""S3-compatible object storage for uploaded statement PDFs.

Uses boto3 rather than the `minio` client so the same code runs unchanged against real
AWS S3 — MinIO only differs by endpoint URL and credentials.
"""

from functools import cache

import boto3
from botocore.exceptions import ClientError

from config import settings

BUCKET = settings.STATEMENTS_BUCKET
ENDPOINT_URL = settings.MINIO_ENDPOINT_URL


@cache
def get_client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=settings.MINIO_ROOT_USER,
        aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
    )


def ensure_bucket() -> None:
    """Create the bucket if it isn't there. Cheaper than a compose init container."""
    client = get_client()
    try:
        client.head_bucket(Bucket=BUCKET)
    except ClientError:
        client.create_bucket(Bucket=BUCKET)


def object_key_for(digest: str) -> str:
    """Content-addressed key: the same bytes always land on the same object."""
    return f"statements/{digest}.pdf"


def put_pdf(key: str, data: bytes) -> str:
    get_client().put_object(Bucket=BUCKET, Key=key, Body=data, ContentType="application/pdf")
    return key


def get_pdf(key: str) -> bytes:
    return get_client().get_object(Bucket=BUCKET, Key=key)["Body"].read()
