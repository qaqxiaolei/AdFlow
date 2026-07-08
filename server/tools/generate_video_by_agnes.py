from typing import Annotated, Optional, Any, Union
from pydantic import BaseModel, Field
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.runnables import RunnableConfig
from tools.video_generation.video_generation_core import generate_video_with_provider
from tools.video_generation.video_prompt_utils import enhance_video_prompt
from .utils.image_utils import process_input_image


def _parse_input_images(input_images: Any) -> list[str] | None:
    if input_images is None:
        return None
    
    if isinstance(input_images, list):
        return input_images
    
    if isinstance(input_images, str):
        v = input_images.strip()
        
        try:
            import json
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        
        if v.startswith('[') and v.endswith(']'):
            try:
                parsed = eval(v)
                if isinstance(parsed, list):
                    return parsed
            except (SyntaxError, ValueError, NameError):
                pass
            
            inner = v[1:-1].strip()
            if inner:
                items = []
                current_item = []
                in_quotes = False
                quote_char = ''
                for char in inner:
                    if char in ('"', "'"):
                        if in_quotes and char == quote_char:
                            in_quotes = False
                        elif not in_quotes:
                            in_quotes = True
                            quote_char = char
                        current_item.append(char)
                    elif char == ',' and not in_quotes:
                        item_str = ''.join(current_item).strip().strip("'\"")
                        if item_str:
                            items.append(item_str)
                        current_item = []
                    else:
                        current_item.append(char)
                if current_item:
                    item_str = ''.join(current_item).strip().strip("'\"")
                    if item_str:
                        items.append(item_str)
                return items
        
        return [v]
    
    return None


class GenerateVideoByAgnesInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. The prompt for video generation. Describe what you want to see in the video."
    )
    resolution: str = Field(
        default="480p",
        description="Optional. The resolution of the video. Use 480p if not explicitly specified by user. Allowed values: 480p, 1080p."
    )
    duration: int = Field(
        default=10,
        description="Optional. The duration of the video in seconds. Use 10 by default. Allowed values: 5, 10, 15. Must not exceed 15 seconds."
    )
    aspect_ratio: str = Field(
        default="16:9",
        description="Optional. The aspect ratio of the video. Allowed values: 1:1, 16:9, 9:16, 4:3, 21:9"
    )
    ratio: str = Field(
        default="16:9",
        description="Optional. The ratio of the video, same as aspect_ratio. Allowed values: 1:1, 16:9, 9:16, 4:3, 21:9"
    )
    input_images: Union[list[str], str, None] = Field(
        default=None,
        description="Optional. Images to use as reference or first frame. Pass a list of image_id here, e.g. ['im_jurheut7.png']."
    )
    quantity: int = Field(
        default=1,
        description="Optional. The number of videos to generate. Use 1 by default. Allowed values: 1, 2."
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool("generate_video_by_agnes",
      description="使用 Agnes AI 视频模型生成视频。提示词必须使用英文，包含详细的视觉描述。",
      args_schema=GenerateVideoByAgnesInputSchema)
async def generate_video_by_agnes(
    prompt: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    resolution: str = "480p",
    duration: int = 10,
    aspect_ratio: str = "16:9",
    ratio: str = "16:9",
    input_images: Any = None,
    quantity: int = 1,
) -> str:
    processed_input_images = None
    
    parsed_images = _parse_input_images(input_images)
    has_reference_image = parsed_images and len(parsed_images) > 0
    print(f"🎥 [GenerateVideo] 解析 input_images: 原始={repr(input_images)}, 解析后={parsed_images}, 有参考图={has_reference_image}")
    
    if has_reference_image:
        processed_input_images = []
        for img in parsed_images:
            processed_image = await process_input_image(img)
            if processed_image:
                processed_input_images.append(processed_image)
                print(f"🎥 [GenerateVideo] 使用输入图片: {img}")
            else:
                print(f"⚠️ [GenerateVideo] 处理图片失败: {img}, 跳过...")
        
        if len(processed_input_images) == 0:
            raise ValueError(
                "未能处理任何输入图片。请检查图片是否存在且有效。")

    actual_ratio = ratio if ratio else aspect_ratio
    print(f"🎥 [GenerateVideo] 使用比例: {actual_ratio}, 生成数量: {quantity}")

    prompt_result = enhance_video_prompt(
        original_prompt=prompt,
        aspect_ratio=actual_ratio,
        has_reference_image=has_reference_image,
        quantity=quantity,
    )

    print(f"🎥 [GenerateVideo] 处理后的提示词: {prompt_result['prompt'][:100]}...")
    if 'negative_prompt' in prompt_result:
        print(f"🎥 [GenerateVideo] 负面提示词: {prompt_result['negative_prompt'][:100]}...")

    if quantity > 1 and 'prompts' in prompt_result:
        results = []
        for i, p in enumerate(prompt_result['prompts'], 1):
            print(f"🎥 [GenerateVideo] 生成第 {i}/{quantity} 个视频")
            result = await generate_video_with_provider(
                prompt=p['prompt'],
                resolution=resolution,
                duration=duration,
                aspect_ratio=actual_ratio,
                model="agnes-video-v2.0",
                tool_call_id=tool_call_id,
                config=config,
                input_images=processed_input_images,
                ratio=actual_ratio,
                negative_prompt=p.get('negative_prompt', ''),
            )
            results.append(result)
        return "\n\n".join(results)
    else:
        return await generate_video_with_provider(
            prompt=prompt_result['prompt'],
            resolution=resolution,
            duration=duration,
            aspect_ratio=actual_ratio,
            model="agnes-video-v2.0",
            tool_call_id=tool_call_id,
            config=config,
            input_images=processed_input_images,
            ratio=actual_ratio,
            negative_prompt=prompt_result.get('negative_prompt', ''),
        )


__all__ = ["generate_video_by_agnes"]
