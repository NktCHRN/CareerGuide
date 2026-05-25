"""Integration with S3-compatible storage (MinIO) via boto3.

career-service does not upload photos itself — it hands the admin a presigned
PUT URL and serves the frontend a presigned GET URL for a profession photo.
Photo layout:  professions/{profession_id}.{jpg|png|webp}; default:
professions/_default.jpg. boto3 is synchronous — the async wrappers run the
calls in a thread pool.
"""
from __future__ import annotations

import asyncio
from functools import lru_cache

import boto3
from botocore.client import Config

from app.config import settings

DEFAULT_PHOTO_KEY = "professions/_default.jpg"

# content-type → file extension for the photo object key.
_CONTENT_TYPE_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_PROBE_EXTENSIONS = ("jpg", "png", "webp")


@lru_cache
def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        # Fail fast when MinIO is unreachable so the details endpoint stays responsive.
        config=Config(
            signature_version="s3v4",
            connect_timeout=2,
            read_timeout=2,
            retries={"max_attempts": 1},
        ),
    )


def photo_key_for(profession_id: int, content_type: str) -> str:
    ext = _CONTENT_TYPE_EXT.get((content_type or "").lower(), "jpg")
    return f"professions/{profession_id}.{ext}"


def _object_exists(key: str) -> bool:
    # Best-effort: any error (missing object, MinIO unreachable) → treated as absent.
    try:
        _client().head_object(Bucket=settings.S3_BUCKET, Key=key)
        return True
    except Exception:  # noqa: BLE001
        return False


def _presigned_get(key: str, ttl: int) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=ttl,
    )


def _presigned_put(key: str, content_type: str, ttl: int) -> str:
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=ttl,
    )


def _resolve_photo(profession_id: int, photo_key: str | None, ttl: int) -> str:
    """Returns a presigned GET URL: the explicit key, a probed id-based key, or the default."""
    if photo_key and _object_exists(photo_key):
        return _presigned_get(photo_key, ttl)
    for ext in _PROBE_EXTENSIONS:
        key = f"professions/{profession_id}.{ext}"
        if _object_exists(key):
            return _presigned_get(key, ttl)
    return _presigned_get(DEFAULT_PHOTO_KEY, ttl)


async def photo_url(profession_id: int, photo_key: str | None = None) -> str:
    """Always returns a URL: the profession's photo if present, otherwise the default."""
    return await asyncio.to_thread(
        _resolve_photo, profession_id, photo_key, settings.PHOTO_PRESIGN_TTL_SECONDS
    )


async def presigned_put_url(profession_id: int, content_type: str) -> tuple[str, str]:
    """Returns (presigned PUT url, object key) for uploading a profession photo."""
    key = photo_key_for(profession_id, content_type)
    url = await asyncio.to_thread(
        _presigned_put, key, content_type, settings.PHOTO_PRESIGN_TTL_SECONDS
    )
    return url, key
