"""Read-only S3 (MinIO) access for resume PDFs.

user-service uploads resumes to `resumes/{user_id}/{uuid}.pdf` and announces
them via `user.resume.uploaded`; the worker downloads the object by its
`s3_key`. boto3 is synchronous, so the blocking call runs in a thread pool.
"""
from __future__ import annotations

import asyncio
from functools import lru_cache

import boto3
from botocore.client import Config

from app.config import settings


@lru_cache
def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=30),
    )


def _download(key: str) -> bytes:
    obj = _client().get_object(Bucket=settings.S3_BUCKET, Key=key)
    return obj["Body"].read()


async def download_bytes(key: str) -> bytes:
    """Download an object's bytes by key (raises on missing object / transport error)."""
    return await asyncio.to_thread(_download, key)
