"""
Agnes API 路由常量定义

本文件统一管理 Agnes AI 的所有 API 接口地址，
避免在多个文件中分散定义导致路径错误。

使用方式：
    from tools.agnes_api_routes import AGNES_IMAGE_API_ROUTE, AGNES_VIDEO_API_ROUTE

示例：
    api_url = f"{base_url}{AGNES_IMAGE_API_ROUTE}"
"""

AGNES_IMAGE_API_ROUTE = "/images/generations"
"""图片生成接口路由"""

AGNES_VIDEO_API_ROUTE = "/videos"
"""视频生成接口路由"""

AGNES_VIDEO_POLL_ROUTE = "/videos/{task_id}"
"""视频任务状态轮询接口路由"""

AGNES_AGNESAPI_POLL_ROUTE = "/agnesapi"
"""视频任务状态轮询备用接口路由（使用 video_id）"""


def build_image_api_url(base_url: str) -> str:
    """
    构建图片生成完整 API URL

    Args:
        base_url: 基础 URL，如 "https://apihub.agnes-ai.com/v1"

    Returns:
        完整的图片生成 API URL
    """
    clean_base = base_url.rstrip("/")
    return f"{clean_base}{AGNES_IMAGE_API_ROUTE}"


def build_video_api_url(base_url: str) -> str:
    """
    构建视频生成完整 API URL

    Args:
        base_url: 基础 URL，如 "https://apihub.agnes-ai.com/v1"

    Returns:
        完整的视频生成 API URL
    """
    clean_base = base_url.rstrip("/")
    return f"{clean_base}{AGNES_VIDEO_API_ROUTE}"


def build_video_poll_url(base_url: str, task_id: str) -> str:
    """
    构建视频任务状态轮询完整 URL

    Args:
        base_url: 基础 URL，如 "https://apihub.agnes-ai.com/v1"
        task_id: 任务 ID

    Returns:
        完整的视频任务状态轮询 URL
    """
    clean_base = base_url.rstrip("/")
    return f"{clean_base}{AGNES_VIDEO_POLL_ROUTE.format(task_id=task_id)}"


def get_api_root(base_url: str) -> str:
    """
    获取 API 根地址（移除 /v1 后缀）

    Args:
        base_url: 基础 URL，如 "https://apihub.agnes-ai.com/v1"

    Returns:
        API 根地址，如 "https://apihub.agnes-ai.com"
    """
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url[:-3]
    return url


__all__ = [
    "AGNES_IMAGE_API_ROUTE",
    "AGNES_VIDEO_API_ROUTE",
    "AGNES_VIDEO_POLL_ROUTE",
    "AGNES_AGNESAPI_POLL_ROUTE",
    "build_image_api_url",
    "build_video_api_url",
    "build_video_poll_url",
    "get_api_root",
]
