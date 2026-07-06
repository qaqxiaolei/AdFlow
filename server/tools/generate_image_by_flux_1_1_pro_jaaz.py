from typing import Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import tool, InjectedToolCallId  # type: ignore
from langchain_core.runnables import RunnableConfig
from tools.utils.image_generation_core import generate_image_with_provider


class GenerateImageByFlux11ProInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. The prompt for image generation. If you want to edit an image, please describe what you want to edit in the prompt."
    )
    aspect_ratio: str = Field(
        description="Required. Aspect ratio of the image, only these values are allowed: 1:1, 16:9, 4:3, 3:4, 9:16. Choose the best fitting aspect ratio according to the prompt. Best ratio for posters is 3:4"
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool("generate_image_by_flux_1_1_pro",
      description="使用 Flux 1.1 Pro 模型通过文本提示生成图像。该模型不支持输入图像作为参考或编辑。使用此模型进行高质量图像生成。支持多个提供商自动降级。提示词必须使用中文。",
      args_schema=GenerateImageByFlux11ProInputSchema)
async def generate_image_by_flux_1_1_pro(
    prompt: str,
    aspect_ratio: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    """
    Generate an image using Flux 1.1 Pro model via the provider framework
    """
    ctx = config.get('configurable', {})
    canvas_id = ctx.get('canvas_id', '')
    session_id = ctx.get('session_id', '')

    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider='jaaz',
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        model="black-forest-labs/flux-1.1-pro",
        input_images=None,
    )


# Export the tool for easy import
__all__ = ["generate_image_by_flux_1_1_pro"]
