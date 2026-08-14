"""
Agnes AI 图像生成工具

使用 Agnes AI 图像模型生成图片，支持模型自动降级和预校验机制。
"""

from typing import Annotated, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from pydantic import BaseModel, Field

from tools.agnes_model_config import AGNES_IMAGE_MODEL_DEFAULT
from tools.utils.image_generation_core import generate_image_with_provider


class GenerateImageByAgnesInputSchema(BaseModel):
    prompt: str = Field(
        description=(
            "Required. Image generation prompt with detailed visual description. "
            "Prefer Chinese; keep all scene details from the user."
        )
    )
    aspect_ratio: str = Field(
        default="1:1",
        description="Aspect ratio: 1:1, 16:9, 9:16, 4:3, or 3:4",
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool(
    "generate_image_by_agnes",
    description=(
        "Generate an image with Agnes AI image model. "
        "Always pass a non-empty prompt and the user-requested aspect_ratio."
    ),
    args_schema=GenerateImageByAgnesInputSchema,
    return_direct=False,
)
async def generate_image_by_agnes(
    prompt: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    aspect_ratio: Optional[str] = "1:1",
) -> str:
    """使用 Agnes AI 图像模型生成图片。"""
    ctx = config.get("configurable", {}) if config else {}
    canvas_id = ctx.get("canvas_id", "")
    session_id = ctx.get("session_id", "")
    user_id = ctx.get("user_id")

    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider="agnes",
        model=AGNES_IMAGE_MODEL_DEFAULT,
        prompt=prompt,
        aspect_ratio=aspect_ratio or "1:1",
        user_id=user_id,
    )


__all__ = ["generate_image_by_agnes"]
