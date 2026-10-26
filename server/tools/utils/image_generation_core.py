"""
Image generation core module
Contains the main orchestration logic for image generation across different providers
"""

from typing import Optional, Dict, Any
from tools.utils.image_utils import process_input_image
from ..image_providers.image_base_provider import ImageProviderBase

# 导入所有提供商以确保自动注册 (不要删除这些导入)
from ..image_providers.agnes_provider import AgnesImageProvider
from ..image_providers.openai_provider import OpenAIImageProvider
from ..image_providers.replicate_provider import ReplicateImageProvider
from ..image_providers.volces_provider import VolcesProvider
from ..image_providers.wavespeed_provider import WavespeedProvider

# from ..image_providers.comfyui_provider import ComfyUIProvider
from .image_canvas_utils import (
    save_image_to_canvas,
)
from .image_prompt_utils import enhance_image_prompt


IMAGE_PROVIDERS: dict[str, ImageProviderBase] = {
    "agnes": AgnesImageProvider(),
    "openai": OpenAIImageProvider(),
    "replicate": ReplicateImageProvider(),
    "volces": VolcesProvider(),
    "wavespeed": WavespeedProvider(),
}


async def generate_image_with_provider(
    canvas_id: str,
    session_id: str,
    provider: str,
    model: str,
    # image generator args
    prompt: str,
    aspect_ratio: str = "1:1",
    input_images: Optional[list[str]] = None,
    user_id: Optional[str] = None,
) -> str:
    """
    通用图像生成函数，支持不同的模型和提供商。
    积分在前端发送时通过 POST /api/billing/consume 扣除，这里不再扣费。
    """

    provider_instance = IMAGE_PROVIDERS.get(provider)
    if not provider_instance:
        raise ValueError(f"Unknown provider: {provider}")

    # Process input images for the provider
    processed_input_images: list[str] | None = None
    if input_images:
        processed_input_images = []
        for image_path in input_images:
            processed_image = await process_input_image(image_path)
            if processed_image:
                processed_input_images.append(processed_image)

        print(f"Using {len(processed_input_images)} input images for generation")

    enhanced_prompt = enhance_image_prompt(prompt)
    if enhanced_prompt != (prompt or "").strip():
        print("🖼️ [ImagePrompt] applied promotional/scene constraints")

    # Prepare metadata with all generation parameters
    metadata: Dict[str, Any] = {
        "prompt": enhanced_prompt,
        "original_prompt": prompt,
        "model": model,
        "provider": provider,
        "aspect_ratio": aspect_ratio,
        "input_images": input_images or [],
    }

    mime_type, width, height, filename = await provider_instance.generate(
        prompt=enhanced_prompt,
        model=model,
        aspect_ratio=aspect_ratio,
        input_images=processed_input_images,
        metadata=metadata,
    )

    image_url = await save_image_to_canvas(
        session_id, canvas_id, filename, mime_type, width, height
    )

    return (
        f"image generated successfully "
        f"![image_id: {filename}]({image_url})"
    )
