"""
Agnes AI 图像生成工具

使用 Agnes AI 图像模型生成图片，支持模型自动降级和预校验机制。

核心特性：
1. 模型兼容兜底：主模型不可用时自动切换备用模型
2. 预校验机制：请求前检查模型是否在白名单中
3. 清晰错误提示：单独处理 model_not_found 错误
4. 可配置化：模型名称从配置文件读取，不再硬编码
"""

from typing import Optional
from langchain_core.tools import tool
from tools.utils.image_generation_core import generate_image_with_provider
from tools.agnes_model_config import AGNES_IMAGE_MODEL_DEFAULT


@tool("generate_image_by_agnes", return_direct=False)
async def generate_image_by_agnes(
    prompt: str,
    aspect_ratio: Optional[str] = "1:1",
) -> str:
    """
    使用 Agnes AI 图像模型生成图片。

    参数:
        prompt: 图像生成提示词（必须使用英文，包含详细的视觉描述）
        aspect_ratio: 图像宽高比，可选值: 1:1, 16:9, 9:16, 4:3, 3:4
    """
    # 【模型参数可配置化】从配置文件读取模型名，不再硬编码
    return await generate_image_with_provider(
        canvas_id="",
        session_id="",
        provider='agnes',
        model=AGNES_IMAGE_MODEL_DEFAULT,
        prompt=prompt,
        aspect_ratio=aspect_ratio,
    )


__all__ = ["generate_image_by_agnes"]
