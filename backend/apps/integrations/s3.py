"""
backend.apps.integrations.s3
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
AWS S3 service layer — upload, download, presigned URLs, delete.

Phase 6.2 — AWS S3 Integration (Week 18)

Tools implemented:
  - upload_to_s3(file_path, bucket, key)
  - download_from_s3(bucket, key, dest_path)
  - get_presigned_url(bucket, key, expiry_seconds)
  - delete_from_s3(bucket, key)
"""

from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

# ── Configuration from environment ────────────────────────────────────────────

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME") or os.environ.get(
    "AWS_S3_BUCKET_NAME", ""
)

# Presigned URL expiry — default 1 hour (Phase 6.2 spec)
DEFAULT_PRESIGNED_EXPIRY = int(os.environ.get("AWS_PRESIGNED_URL_EXPIRY", 3600))


def _s3_client():
    """Return a boto3 S3 client configured from env vars."""
    kwargs: dict = {"region_name": AWS_REGION}
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
    return boto3.client("s3", **kwargs)


# ── Tool: upload_to_s3 ────────────────────────────────────────────────────────


def upload_to_s3(
    file_path: str,
    bucket: str = AWS_S3_BUCKET_NAME,
    key: Optional[str] = None,
    public: bool = False,
) -> dict:
    """
    Upload a local file to S3.

    Args:
        file_path: Absolute path to the local file.
        bucket:    S3 bucket name.
        key:       S3 object key (defaults to basename of file_path).
        public:    If True, set ACL to public-read (only if bucket allows it).

    Returns:
        dict with {bucket, key, url, presigned_url}
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    s3 = _s3_client()
    object_key = key or path.name

    mime_type, _ = mimetypes.guess_type(str(path))
    mime_type = mime_type or "application/octet-stream"

    extra_args: dict = {"ContentType": mime_type}
    if public:
        extra_args["ACL"] = "public-read"

    try:
        s3.upload_file(str(path), bucket, object_key, ExtraArgs=extra_args)
        logger.info("Uploaded '%s' to s3://%s/%s", path.name, bucket, object_key)
    except (ClientError, NoCredentialsError) as exc:
        logger.error("S3 upload failed: %s", exc)
        raise

    s3_url = f"https://{bucket}.s3.{AWS_REGION}.amazonaws.com/{object_key}"
    presigned = get_presigned_url(bucket, object_key)

    return {
        "bucket": bucket,
        "key": object_key,
        "url": s3_url,
        "presigned_url": presigned,
    }


# ── Tool: download_from_s3 ────────────────────────────────────────────────────


def download_from_s3(
    bucket: str,
    key: str,
    dest_path: str,
) -> str:
    """
    Download a file from S3 to a local path.

    Returns the destination file path string.
    """
    s3 = _s3_client()
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        s3.download_file(bucket, key, str(dest))
        logger.info("Downloaded s3://%s/%s → %s", bucket, key, dest)
    except (ClientError, NoCredentialsError) as exc:
        logger.error("S3 download failed: %s", exc)
        raise

    return str(dest)


# ── Tool: get_presigned_url ───────────────────────────────────────────────────


def get_presigned_url(
    bucket: str,
    key: str,
    expiry_seconds: int = DEFAULT_PRESIGNED_EXPIRY,
) -> str:
    """
    Generate a presigned URL for secure, time-limited file access.

    Args:
        bucket:         S3 bucket name.
        key:            S3 object key.
        expiry_seconds: URL lifetime in seconds (default: 3600 = 1 hour).

    Returns:
        Presigned URL string.
    """
    s3 = _s3_client()
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry_seconds,
        )
        logger.debug(
            "Generated presigned URL for s3://%s/%s (expires in %ds)",
            bucket,
            key,
            expiry_seconds,
        )
        return url
    except (ClientError, NoCredentialsError) as exc:
        logger.error("Presigned URL generation failed: %s", exc)
        raise


# ── Tool: delete_from_s3 ──────────────────────────────────────────────────────


def delete_from_s3(bucket: str, key: str) -> bool:
    """
    Delete a file from S3.

    Returns True on success, False on failure.
    """
    s3 = _s3_client()
    try:
        s3.delete_object(Bucket=bucket, Key=key)
        logger.info("Deleted s3://%s/%s", bucket, key)
        return True
    except (ClientError, NoCredentialsError) as exc:
        logger.error("S3 delete failed: %s", exc)
        return False


# ── Utility: migrate local file to S3 ─────────────────────────────────────────


def migrate_file_to_s3(
    local_path: str,
    s3_prefix: str = "documents/",
    bucket: str = AWS_S3_BUCKET_NAME,
    delete_local: bool = False,
) -> str:
    """
    Upload a local file to S3 under the given prefix.
    Optionally delete the local copy after successful upload.

    Returns the presigned URL.
    """
    path = Path(local_path)
    key = f"{s3_prefix.rstrip('/')}/{path.name}"
    result = upload_to_s3(str(path), bucket=bucket, key=key)

    if delete_local and path.exists():
        path.unlink()
        logger.info("Deleted local file after S3 migration: %s", local_path)

    return result["presigned_url"]
