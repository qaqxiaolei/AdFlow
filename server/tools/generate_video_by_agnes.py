from typing import Annotated, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool, InjectedToolCallId  # type: ignore
from langchain_core.runnables import RunnableConfig
from tools.video_generation.video_generation_core import generate_video_with_provider
from .utils.image_utils import process_input_image


class GenerateVideoByAgnesInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. The prompt for video generation. Describe what you want to see in the video."
    )
    resolution: str = Field(
        default="480p",
        description="Optional. The resolution of the video. Use 480p if not explicitly specified by user. Allowed values: 480p, 1080p."
    )
    duration: int = Field(
        default=5,
        description="Optional. The duration of the video in seconds. Use 5 by default. Allowed values: 5, 10."
    )
    aspect_ratio: str = Field(
        default="16:9",
        description="Optional. The aspect ratio of the video. Allowed values: 1:1, 16:9, 9:16, 4:3, 21:9"
    )
    input_images: list[str] | None = Field(
        default=None,
        description="Optional. Images to use as reference or first frame. Pass a list of image_id here, e.g. ['im_jurheut7.png']."
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool("generate_video_by_agnes",
      description="使用 Agnes AI 视频模型生成视频。提示词必须使用中文。",
      args_schema=GenerateVideoByAgnesInputSchema)
async def generate_video_by_agnes(
    prompt: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    resolution: str = "480p",
    duration: int = 5,
    aspect_ratio: str = "16:9",
    input_images: list[str] | None = None,
) -> str:
    processed_input_images = None
    if input_images and len(input_images) > 0:
        processed_input_images = []
        for img in input_images:
            processed_image = await process_input_image(img)
            if processed_image:
                processed_input_images.append(processed_image)
                print(f"Using input image for video generation: {img}")
            else:
                print(f"Warning: Failed to process input image: {img}, skipping...")
        
        if len(processed_input_images) == 0:
            raise ValueError(
                "Failed to process any input images. Please check if the images exist and are valid.")

    return await generate_video_with_provider(
        prompt=prompt,
        resolution=resolution,
        duration=duration,
        aspect_ratio=aspect_ratio,
        model="agnes-video-v2.0",
        tool_call_id=tool_call_id,
        config=config,
        input_images=processed_input_images,
    )


__all__ = ["generate_video_by_agnes"]