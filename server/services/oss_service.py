"""Aliyun OSS helpers for generated media (videos / posters)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_bucket = None
_warned = False


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    except Exception:
        pass


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    # Normalize unicode dashes that sometimes appear when pasting from docs
    value = os.environ.get(name, default).strip()
    return (
        value.replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
    )


def is_oss_configured() -> bool:
    return bool(
        _env("OSS_ACCESS_KEY_ID")
        and _env("OSS_ACCESS_KEY_SECRET")
        and _env("OSS_ENDPOINT")
        and _env("OSS_BUCKET")
    )


def _get_bucket():
    global _bucket, _warned
    if _bucket is not None:
        return _bucket
    if not is_oss_configured():
        if not _warned:
            print("[oss] not configured — videos stay on local /api/file/")
            _warned = True
        return None
    try:
        import oss2
    except ImportError as exc:
        raise RuntimeError(
            "未安装 oss2，请执行: pip install oss2"
        ) from exc

    endpoint = _env("OSS_ENDPOINT")
    if not endpoint.startswith("http"):
        endpoint = f"https://{endpoint}"

    auth = oss2.Auth(_env("OSS_ACCESS_KEY_ID"), _env("OSS_ACCESS_KEY_SECRET"))
    _bucket = oss2.Bucket(auth, endpoint, _env("OSS_BUCKET"))
    return _bucket


def public_object_url(object_key: str) -> str:
    """Build public HTTPS URL for an object."""
    custom = _env("OSS_PUBLIC_BASE_URL").rstrip("/")
    if custom:
        return f"{custom}/{object_key.lstrip('/')}"

    endpoint = _env("OSS_ENDPOINT")
    if endpoint.startswith("http"):
        endpoint = endpoint.split("://", 1)[1]
    endpoint = endpoint.rstrip("/")
    bucket = _env("OSS_BUCKET")
    return f"https://{bucket}.{endpoint}/{object_key.lstrip('/')}"


def upload_file(
    local_path: str,
    object_key: str,
    content_type: Optional[str] = None,
) -> str:
    """
    Upload a local file to OSS and return its public URL.
    Objects are set to public-read so the frontend can play them directly.
    """
    bucket = _get_bucket()
    if bucket is None:
        raise RuntimeError("OSS is not configured")

    headers = {}
    if content_type:
        headers["Content-Type"] = content_type

    # public-read so browsers / WeChat can stream without signed cookies
    bucket.put_object_from_file(
        object_key,
        local_path,
        headers=headers or None,
    )
    try:
        bucket.put_object_acl(object_key, "public-read")
    except Exception as acl_err:
        print(f"[oss] put_object_acl warning: {acl_err}")

    url = public_object_url(object_key)
    print(f"[oss] uploaded {local_path} -> {url}")
    return url


async def upload_file_async(
    local_path: str,
    object_key: str,
    content_type: Optional[str] = None,
) -> str:
    import asyncio

    return await asyncio.to_thread(upload_file, local_path, object_key, content_type)
