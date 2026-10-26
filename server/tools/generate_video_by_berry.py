"""Berry 1.0 视频工具。提示词增强与数量逻辑复用 Seedance，生成走 MuleRouter。"""

from typing import Annotated, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from pydantic import BaseModel, Field

from tools.generate_video_by_agnes import (
    GenerateVideoByAgnesInputSchema,
    run_video_generation,
)

BERRY_VIDEO_MODEL = "berry-1.0"


class GenerateVideoByBerryInputSchema(GenerateVideoByAgnesInputSchema):
    resolution: str = Field(
        default="480p",
        description="可选。视频分辨率。默认 480p。可选值：480p、720p、1080p。",
    )
    duration: int = Field(
        default=5,
        description="可选。视频时长（秒）。Berry 支持 2 到 30 秒，默认 5。",
    )


@tool(
    "generate_video_by_berry",
    description=(
        "使用 Berry 1.0 视频模型（MuleRouter）生成视频。"
        "仅当用户在模型列表中选择了 Berry 1.0，或明确要求 Berry 时调用。"
        "不要在用户选择 Seedance 2.0 时调用本工具。"
        "提示词使用中文。用户消息中的 <aspect_ratio> 和 <quantity> 必须原样传入。"
    ),
    args_schema=GenerateVideoByBerryInputSchema,
)
async def generate_video_by_berry(
    prompt: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    resolution: str = "480p",
    duration: int = 5,
    aspect_ratio: str = "9:16",
    ratio: str = "9:16",
    input_images: Any = None,
    quantity: int = 1,
) -> str:
    return await run_video_generation(
        prompt=prompt,
        config=config,
        tool_call_id=tool_call_id,
        resolution=resolution,
        duration=duration,
        aspect_ratio=aspect_ratio,
        ratio=ratio,
        input_images=input_images,
        quantity=quantity,
        video_model=BERRY_VIDEO_MODEL,
        video_provider="mulerouter",
    )


__all__ = ["generate_video_by_berry"]
