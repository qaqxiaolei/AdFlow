"""Aliyun OSS helpers for generated media (videos / posters)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple

_bucket = None
_config_logged = False


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


def missing_oss_keys() -> List[str]:
    required = (
        "OSS_ACCESS_KEY_ID",
        "OSS_ACCESS_KEY_SECRET",
        "OSS_ENDPOINT",
        "OSS_BUCKET",
    )
    return [name for name in required if not _env(name)]


def is_oss_configured() -> bool:
    return not missing_oss_keys()


def log_oss_status(force: bool = False) -> None:
    """Print once (or force) whether OSS is ready — easy to spot in server logs."""
    global _config_logged
    if _config_logged and not force:
        return
    _config_logged = True
    missing = missing_oss_keys()
    if missing:
        print(
            "[oss] ❌ 未完整配置，视频将只用本地 /api/file/ "
            f"（云服务器上无法访问本机文件）。缺少: {', '.join(missing)}"
        )
        return
    print(
        "[oss] ✅ 已配置 "
        f"bucket={_env('OSS_BUCKET')} endpoint={_env('OSS_ENDPOINT')}"
    )


def _get_bucket():
    global _bucket
    log_oss_status()
    if _bucket is not None:
        return _bucket
    if not is_oss_configured():
        return None
    try:
        import oss2
    except ImportError as exc:
        raise RuntimeError("未安装 oss2，请执行: pip install oss2") from exc

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
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"本地文件不存在，无法上传 OSS: {local_path}")

    bucket = _get_bucket()
    if bucket is None:
        missing = ", ".join(missing_oss_keys()) or "unknown"
        raise RuntimeError(f"OSS 未配置（缺少 {missing}）")

    size = os.path.getsize(local_path)
    print(f"[oss] 开始上传 {local_path} ({size} bytes) -> {object_key}")

    headers = {}
    if content_type:
        headers["Content-Type"] = content_type

    try:
        bucket.put_object_from_file(
            object_key,
            local_path,
            headers=headers or None,
        )
    except Exception as exc:
        raise RuntimeError(f"OSS put_object 失败: {exc}") from exc

    try:
        bucket.put_object_acl(object_key, "public-read")
    except Exception as acl_err:
        print(
            f"[oss] ⚠️ 设置 public-read 失败（Bucket 可能是私有且禁止改 ACL）: {acl_err}"
        )
        print(
            "[oss] 请到控制台把 Bucket 读写权限改为「公共读」，"
            "否则外链可能 403，云端手机打不开视频"
        )

    url = public_object_url(object_key)
    print(f"[oss] ✅ 上传成功 -> {url}")
    return url


async def upload_file_async(
    local_path: str,
    object_key: str,
    content_type: Optional[str] = None,
) -> str:
    import asyncio

    return await asyncio.to_thread(upload_file, local_path, object_key, content_type)


def describe_playback_url(file_url: str) -> Tuple[str, bool]:
    """Return (human label, is_oss)."""
    if file_url.startswith("http://") or file_url.startswith("https://"):
        if "aliyuncs.com" in file_url or ".oss-" in file_url:
            return ("OSS 公网地址", True)
        return ("外部 HTTPS 地址", True)
    return ("本地 /api/file/（仅本机可播）", False)
