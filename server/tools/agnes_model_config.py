"""
Agnes AI 模型配置常量

本文件统一管理 Agnes AI 的所有模型配置，
避免在多个文件中硬编码模型名称导致维护困难。

使用方式：
    from tools.agnes_model_config import AGNES_IMAGE_MODELS, AGNES_VIDEO_MODELS

示例：
    primary_model = AGNES_IMAGE_MODELS[0]
    fallback_models = AGNES_IMAGE_MODELS[1:]
"""

from typing import List

# ==================== 图像模型配置 ====================
AGNES_IMAGE_MODELS: List[str] = [
    "agnes-image-2.1-flash",
    "agnes-image-2.0-flash",
    "agnes-image-2.1",
    "agnes-image-2.0",
]
"""
Agnes 图像生成模型列表（按优先级排序）

列表中第一个为默认主模型，后续为备用模型。
当主模型调用失败（model_not_found）时，会自动尝试下一个备用模型。

注意：需要确保 API Key 对应的账户有权限访问这些模型。
"""

AGNES_IMAGE_MODEL_DEFAULT: str = AGNES_IMAGE_MODELS[0]
"""默认图像生成模型"""

# ==================== 视频模型配置 ====================
AGNES_VIDEO_MODELS: List[str] = [
    "agnes-video-v2.0",
    "agnes-video-v1.0",
]
"""
Agnes 视频生成模型列表（按优先级排序）

列表中第一个为默认主模型，后续为备用模型。
"""

AGNES_VIDEO_MODEL_DEFAULT: str = AGNES_VIDEO_MODELS[0]
"""默认视频生成模型"""

# ==================== 文本模型配置 ====================
AGNES_TEXT_MODELS: List[str] = [
    "agnes-2.0-flash",
    "agnes-1.0",
]
"""
Agnes 文本生成模型列表（按优先级排序）
"""

AGNES_TEXT_MODEL_DEFAULT: str = AGNES_TEXT_MODELS[0]
"""默认文本生成模型"""


def get_image_models_with_fallback() -> tuple[str, List[str]]:
    """
    获取图像模型的主模型和备用模型列表

    Returns:
        (主模型, 备用模型列表)
    """
    if len(AGNES_IMAGE_MODELS) == 0:
        raise ValueError("未配置任何 Agnes 图像模型")
    return AGNES_IMAGE_MODELS[0], AGNES_IMAGE_MODELS[1:]


def get_video_models_with_fallback() -> tuple[str, List[str]]:
    """
    获取视频模型的主模型和备用模型列表

    Returns:
        (主模型, 备用模型列表)
    """
    if len(AGNES_VIDEO_MODELS) == 0:
        raise ValueError("未配置任何 Agnes 视频模型")
    return AGNES_VIDEO_MODELS[0], AGNES_VIDEO_MODELS[1:]


def is_valid_image_model(model_name: str) -> bool:
    """
    检查模型名是否在图像模型白名单中

    Args:
        model_name: 模型名称

    Returns:
        是否为有效图像模型
    """
    return model_name in AGNES_IMAGE_MODELS


def is_valid_video_model(model_name: str) -> bool:
    """
    检查模型名是否在视频模型白名单中

    Args:
        model_name: 模型名称

    Returns:
        是否为有效视频模型
    """
    return model_name in AGNES_VIDEO_MODELS


__all__ = [
    "AGNES_IMAGE_MODELS",
    "AGNES_IMAGE_MODEL_DEFAULT",
    "AGNES_VIDEO_MODELS",
    "AGNES_VIDEO_MODEL_DEFAULT",
    "AGNES_TEXT_MODELS",
    "AGNES_TEXT_MODEL_DEFAULT",
    "get_image_models_with_fallback",
    "get_video_models_with_fallback",
    "is_valid_image_model",
    "is_valid_video_model",
]
