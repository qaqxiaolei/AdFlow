"""
Agnes AI 图像生成工具

每次调用只生成 1 张独立图片。
需要多张时（用户 <quantity>N</quantity>），由 Agent 调用本工具 N 次，每次一个风格 prompt。
"""

from __future__ import annotations

import re
from typing import Annotated, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from pydantic import BaseModel, Field

from tools.agnes_model_config import AGNES_IMAGE_MODEL_DEFAULT
from tools.utils.image_generation_core import generate_image_with_provider
from tools.utils.image_prompt_utils import enhance_image_prompt, strip_image_control_tags


def _extract_tag_value(text: str, tag: str) -> str | None:
    if not text:
        return None
    match = re.search(
        rf"<{tag}>(.*?)</{tag}>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _get_raw_user_prompt(config: Optional[RunnableConfig]) -> str:
    if not config:
        return ""
    ctx = config.get("configurable", {}) or {}
    return str(ctx.get("user_prompt") or "")


def _resolve_aspect_ratio(
    prompt: str,
    aspect_ratio: str,
    config: Optional[RunnableConfig] = None,
) -> str:
    sources = []
    if config is not None:
        sources.append(_get_raw_user_prompt(config))
    sources.append(prompt or "")
    for source in sources:
        ratio = _extract_tag_value(source, "aspect_ratio")
        if ratio:
            return ratio
    return aspect_ratio or "1:1"


class GenerateImageByAgnesInputSchema(BaseModel):
    prompt: str = Field(
        description=(
            "Required. ONE style only — detailed Chinese visual description for a single "
            "standalone image. Never put 风格一+风格二 or side-by-side collage instructions "
            "in the same prompt. For multiple images, call this tool multiple times."
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
        "Generate exactly ONE standalone image. "
        "If user <quantity> is N, you MUST invoke this tool N separate times "
        "(N parallel calls allowed), each with a different single-style prompt. "
        "Do not combine multiple styles into one prompt or one call."
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
    """使用 Agnes AI 图像模型生成一张独立图片。"""
    ctx = config.get("configurable", {}) if config else {}
    canvas_id = ctx.get("canvas_id", "")
    session_id = ctx.get("session_id", "")
    user_id = ctx.get("user_id")

    resolved_ratio = _resolve_aspect_ratio(prompt, aspect_ratio or "1:1", config)
    clean_prompt = strip_image_control_tags(prompt)
    if not clean_prompt.strip():
        clean_prompt = strip_image_control_tags(
            _get_raw_user_prompt(config) or prompt
        )

    # 单次调用强制单图；增强里已含禁止拼图约束
    final_prompt = enhance_image_prompt(clean_prompt)
    print(f"🖼️ [GenerateImage] single image ratio={resolved_ratio}")

    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider="agnes",
        model=AGNES_IMAGE_MODEL_DEFAULT,
        prompt=final_prompt,
        aspect_ratio=resolved_ratio,
        user_id=user_id,
    )


__all__ = ["generate_image_by_agnes"]
