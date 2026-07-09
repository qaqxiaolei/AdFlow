import asyncio
import re
import time
from typing import Annotated, Optional, Any, Union
from pydantic import BaseModel, Field
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.runnables import RunnableConfig
from tools.video_generation.video_generation_core import generate_video_with_provider
from tools.video_generation.video_prompt_utils import enhance_video_prompt
from tools.video_providers.agnes_provider import VIDEO_CREATE_RATE_LIMIT_SECONDS
from .utils.image_utils import process_input_image

VALID_ASPECT_RATIOS = {"1:1", "16:9", "9:16", "4:3", "21:9", "3:4"}
DEFAULT_ASPECT_RATIO = "9:16"
LEGACY_DEFAULT_ASPECT_RATIO = "16:9"


def _extract_tag_value(text: str, tag: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(
        rf"<{tag}>\s*(.*?)\s*</{tag}>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else None


def _normalize_aspect_ratio(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().replace("/", ":").replace(" ", "")
    if normalized in VALID_ASPECT_RATIOS:
        return normalized
    return None


def _strip_generation_tags(text: str) -> str:
    cleaned = re.sub(
        r"<aspect_ratio>.*?</aspect_ratio>\s*",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(
        r"<quantity>.*?</quantity>\s*",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return cleaned.strip()


def _resolve_aspect_ratio(
    prompt: str,
    aspect_ratio: str,
    ratio: str,
) -> str:
    prompt_ratio = _normalize_aspect_ratio(_extract_tag_value(prompt, "aspect_ratio"))
    if prompt_ratio:
        return prompt_ratio

    for candidate in (ratio, aspect_ratio):
        normalized = _normalize_aspect_ratio(candidate)
        if normalized and normalized != LEGACY_DEFAULT_ASPECT_RATIO:
            return normalized

    return DEFAULT_ASPECT_RATIO


def _get_user_prompt(config: RunnableConfig) -> str:
    configurable = config.get("configurable", {})
    if isinstance(configurable, dict):
        return _strip_generation_tags(configurable.get("user_prompt", ""))
    return ""


def _is_primarily_english(text: str) -> bool:
    if not text.strip():
        return False
    ascii_letters = sum(1 for c in text if c.isascii() and c.isalpha())
    cjk_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    total = ascii_letters + cjk_chars
    if total == 0:
        return False
    return ascii_letters / total > 0.5


def _resolve_prompt(prompt: str, config: RunnableConfig) -> str:
    user_prompt = _get_user_prompt(config)
    cleaned = _strip_generation_tags(prompt or "")

    # AI 常将用户中文需求翻译成英文传入工具；优先保留用户原始中文描述
    if user_prompt.strip():
        if not cleaned.strip() or _is_primarily_english(cleaned):
            if cleaned.strip() and cleaned.strip() != user_prompt.strip():
                print(
                    "🎥 [GenerateVideo] 使用用户原始中文消息作为场景描述"
                    "（忽略 AI 传入的英文 prompt）"
                )
            return user_prompt

    if cleaned.strip():
        return cleaned

    raise ValueError("缺少视频生成提示词 prompt，请提供场景描述")


def _resolve_quantity(prompt: str, quantity: int) -> int:
    prompt_quantity = _extract_tag_value(prompt, "quantity")
    if prompt_quantity:
        try:
            return max(1, min(2, int(prompt_quantity)))
        except ValueError:
            pass
    return max(1, min(2, quantity))


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
        default="",
        description="必填。视频生成提示词，描述希望在视频中看到的画面内容，可使用中文或英文。"
    )
    resolution: str = Field(
        default="480p",
        description="可选。视频分辨率。快速生成请使用 480p。可选值：480p、1080p。"
    )
    duration: int = Field(
        default=10,
        description="可选。视频时长（秒）。快速生成建议使用 10 秒。可选值：5、10、15，最长不超过 15 秒。"
    )
    aspect_ratio: str = Field(
        default="9:16",
        description="可选。视频宽高比。短视频默认 9:16 竖屏。可选值：1:1、16:9、9:16、4:3、21:9。"
    )
    ratio: str = Field(
        default="9:16",
        description="可选。视频比例，与 aspect_ratio 相同。默认 9:16 竖屏。可选值：1:1、16:9、9:16、4:3、21:9。"
    )
    input_images: Union[list[str], str, None] = Field(
        default=None,
        description="可选。参考图或首帧图片。传入 image_id 列表，例如 ['im_jurheut7.png']。"
    )
    quantity: int = Field(
        default=1,
        description="可选。生成视频数量。默认 1 个。可选值：1、2。"
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool("generate_video_by_agnes",
      description="使用 Agnes AI 视频模型生成视频。提示词需包含详细的视觉场景描述（可用中文）。用户消息中的 <aspect_ratio> 和 <quantity> 标签必须原样传入对应参数。",
      args_schema=GenerateVideoByAgnesInputSchema)
async def generate_video_by_agnes(
    prompt: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    resolution: str = "480p",
    duration: int = 10,
    aspect_ratio: str = "9:16",
    ratio: str = "9:16",
    input_images: Any = None,
    quantity: int = 1,
) -> str:
    resolved_prompt = _resolve_prompt(prompt, config)
    actual_ratio = _resolve_aspect_ratio(resolved_prompt, aspect_ratio, ratio)
    resolved_quantity = _resolve_quantity(resolved_prompt, quantity)
    print(
        f"🎥 [GenerateVideo] 使用比例: {actual_ratio}, "
        f"生成数量: {resolved_quantity}"
    )

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

    prompt_result = enhance_video_prompt(
        original_prompt=resolved_prompt,
        aspect_ratio=actual_ratio,
        has_reference_image=has_reference_image,
        quantity=resolved_quantity,
        user_context=_get_user_prompt(config),
    )
    print('🎥 [GenerateVideo] 增强后的提示词', prompt_result)
    if prompt_result.get("prompts"):
        first_prompt = prompt_result["prompts"][0].get("prompt", "")
    else:
        first_prompt = prompt_result.get("prompt", "")
    if "【重要】" in first_prompt or "火锅" in first_prompt:
        print("🎥 [GenerateVideo] 已启用火锅食材/锅底规范约束")

    if resolved_quantity > 1 and 'prompts' in prompt_result:
        for i, p in enumerate(prompt_result['prompts'], 1):
            print(
                f"🎥 [GenerateVideo] 视频 {i} 提示词: "
                f"{p['prompt'][:100]}..."
            )
            if p.get('negative_prompt'):
                print(
                    f"🎥 [GenerateVideo] 视频 {i} 负面提示词: "
                    f"{p['negative_prompt'][:100]}..."
                )

        print(
            f"🎥 [GenerateVideo] 顺序生成 {resolved_quantity} 个视频"
            f"（限流间隔 {VIDEO_CREATE_RATE_LIMIT_SECONDS}s）"
        )

        success_results = []
        failed_results = []
        last_create_at = 0.0

        for i, p in enumerate(prompt_result['prompts'], 1):
            style_label = p.get("style_name", f"视频{i}")
            if i > 1:
                wait_seconds = VIDEO_CREATE_RATE_LIMIT_SECONDS - (
                    time.monotonic() - last_create_at
                )
                if wait_seconds > 0:
                    print(
                        f"🎥 [GenerateVideo] 等待限流窗口 "
                        f"{wait_seconds:.0f}s 后生成第 {i}/{resolved_quantity} 个视频"
                    )
                    await asyncio.sleep(wait_seconds)

            print(f"🎥 [GenerateVideo] 开始生成视频 {i}/{resolved_quantity}（{style_label}）")
            last_create_at = time.monotonic()

            try:
                result = await generate_video_with_provider(
                    prompt=p['prompt'],
                    resolution=resolution,
                    duration=duration,
                    aspect_ratio=actual_ratio,
                    model="agnes-video-v2.0",
                    tool_call_id=f"{tool_call_id}_{i}",
                    config=config,
                    input_images=processed_input_images,
                    ratio=actual_ratio,
                    negative_prompt=p.get('negative_prompt', ''),
                    style_name=style_label,
                    notify_on_error=False,
                )
                success_results.append(f"【{style_label}】{result}")
            except Exception as error:
                print(f"⚠️ [GenerateVideo] 视频 {i}（{style_label}）生成失败: {error}")
                failed_results.append(f"【{style_label}】生成失败: {error}")

        result_parts = success_results + failed_results
        if success_results:
            summary = "\n\n".join(result_parts)
            if failed_results:
                summary += (
                    f"\n\n注意：请求 {resolved_quantity} 个视频，"
                    f"成功 {len(success_results)} 个，失败 {len(failed_results)} 个。"
                    "请如实告知用户哪些风格成功、哪些失败，不要编造未生成的视频链接。"
                )
            return summary
        raise Exception(f"所有 {resolved_quantity} 个视频生成均失败")

    print(f"🎥 [GenerateVideo] 处理后的提示词: {prompt_result['prompt'][:100]}...")
    if prompt_result.get('negative_prompt'):
        print(f"🎥 [GenerateVideo] 负面提示词: {prompt_result['negative_prompt'][:100]}...")

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
