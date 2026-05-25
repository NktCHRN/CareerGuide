"""Integration with S3-compatible storage (MinIO) via boto3.

user-service stores uploaded resumes (`resumes/{user_id}/{uuid}.pdf`) and
serves presigned-GET links to the frontend. boto3 is synchronous — the async
wrappers run the calls in a thread pool.
"""
from __future__ import annotations

import asyncio
import uuid
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
        config=Config(signature_version="s3v4"),
    )


def resume_key(user_id: int) -> str:
    return f"resumes/{user_id}/{uuid.uuid4().hex}.pdf"


def _put(key: str, body: bytes, content_type: str) -> None:
    _client().put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=body,
        ContentType=content_type,
    )


def _presigned_get(key: str, ttl: int) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=ttl,
    )


async def upload_resume(user_id: int, body: bytes) -> str:
    """Uploads a PDF and returns the S3 key."""
    key = resume_key(user_id)
    await asyncio.to_thread(_put, key, body, "application/pdf")
    return key


async def presigned_get_url(key: str, ttl: int | None = None) -> str:
    return await asyncio.to_thread(
        _presigned_get, key, ttl or settings.RESUME_PRESIGN_TTL_SECONDS
    )
