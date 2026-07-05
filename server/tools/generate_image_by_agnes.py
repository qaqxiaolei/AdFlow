from typing import Optional
from langchain_core.tools import tool
from tools.utils.image_generation_core import generate_image_with_provider


@tool("generate_image_by_agnes", return_direct=False)
async def generate_image_by_agnes(
    prompt: str,
    aspect_ratio: Optional[str] = "1:1",
) -> str:
    """
    Generate images using Agnes AI image model.

    Args:
        prompt: Image generation prompt
        aspect_ratio: Image aspect ratio, options: 1:1, 16:9, 9:16, 4:3, 3:4
    """
    return await generate_image_with_provider(
        canvas_id="",
        session_id="",
        provider='agnes',
        model='agnes-image-2.1-flash',
        prompt=prompt,
        aspect_ratio=aspect_ratio,
    )


__all__ = ["generate_image_by_agnes"]