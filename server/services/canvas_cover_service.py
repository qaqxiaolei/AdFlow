import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from services.db_service import db_service
from tools.agnes_model_config import AGNES_IMAGE_MODEL_DEFAULT

_generating_covers: set[str] = set()
DEFAULT_CANVAS_NAMES = frozenset({"", "未命名", "Untitled"})
MAX_CANVAS_NAME_LENGTH = 32


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


def extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return " ".join(parts)
    return ""


def extract_prompt_from_messages(messages: List[Dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") != "user":
            continue
        text = extract_text_from_content(message.get("content", ""))
        text = _strip_generation_tags(text).strip()
        if text:
            return text
    return ""


def build_canvas_name_from_prompt(
    user_prompt: str,
    max_length: int = MAX_CANVAS_NAME_LENGTH,
) -> str:
    cleaned = _strip_generation_tags(user_prompt).strip()
    if not cleaned:
        return "未命名"

    cleaned = re.sub(r"\s+", " ", cleaned)

    topic_match = re.search(
        r"生成(?:一个|一款|一条|一支|一份)?(.{2,24}?)(?:的)?(?:爆款)?(?:宣传)?(?:视频|短片|广告|海报|封面|图片)",
        cleaned,
    )
    if topic_match:
        cleaned = topic_match.group(1).strip("的、，, ")
    else:
        for separator in ("。", "！", "？", "\n", ";", "；", ".", "!", "?"):
            if separator in cleaned:
                first_part = cleaned.split(separator)[0].strip()
                if first_part:
                    cleaned = first_part
                    break

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip() + "…"

    return cleaned or "未命名"


async def apply_canvas_name(
    canvas_id: str,
    prompt: str,
    session_id: Optional[str] = None,
) -> None:
    name = build_canvas_name_from_prompt(prompt)
    if name in DEFAULT_CANVAS_NAMES:
        return

    if session_id:
        await db_service.update_session_title(session_id, name)
        return

    await db_service.rename_canvas(canvas_id, name)


async def _apply_name_with_fallback(
    canvas_id: str,
    prompt: str,
    session_id: Optional[str] = None,
) -> None:
    if prompt:
        await apply_canvas_name(canvas_id, prompt, session_id)
        return

    db_prompt = await db_service.get_canvas_first_user_prompt(canvas_id)
    if db_prompt:
        await apply_canvas_name(canvas_id, db_prompt, session_id)


def schedule_canvas_name_update(
    canvas_id: str,
    messages: Optional[List[Dict[str, Any]]] = None,
    session_id: Optional[str] = None,
) -> None:
    prompt = extract_prompt_from_messages(messages or [])
    asyncio.create_task(_apply_name_with_fallback(canvas_id, prompt, session_id))


def schedule_missing_canvas_names(canvases: List[Dict[str, Any]]) -> None:
    for canvas in canvases:
        if canvas.get("name") not in DEFAULT_CANVAS_NAMES:
            continue
        schedule_canvas_name_update(
            canvas["id"],
            session_id=canvas.get("session_id"),
        )


def build_cover_prompt(user_prompt: str) -> str:
    cleaned = user_prompt.strip() or "餐饮商家宣传"
    return (
        "商业宣传封面海报，竖版构图，高清精美，视觉吸睛，"
        f"适合短视频平台推广，主题内容：{cleaned[:300]}"
    )


async def generate_canvas_cover(canvas_id: str, prompt: str) -> None:
    if not prompt or canvas_id in _generating_covers:
        return

    _generating_covers.add(canvas_id)
    try:
        thumbnail = await db_service.get_canvas_thumbnail(canvas_id)
        if thumbnail:
            return

        from tools.image_providers.agnes_provider import AgnesImageProvider

        cover_prompt = build_cover_prompt(prompt)
        provider = AgnesImageProvider()
        _, _, _, filename = await provider.generate(
            prompt=cover_prompt,
            model=AGNES_IMAGE_MODEL_DEFAULT,
            aspect_ratio="3:4",
        )
        image_url = f"/api/file/{filename}"
        await db_service.update_canvas_thumbnail(canvas_id, image_url)
        print(f"🖼️ [CanvasCover] 封面已生成: {canvas_id} -> {image_url}")
    except Exception as error:
        print(f"⚠️ [CanvasCover] 封面生成失败 ({canvas_id}): {error}")
    finally:
        _generating_covers.discard(canvas_id)


async def _generate_cover_with_fallback(
    canvas_id: str,
    prompt: str,
) -> None:
    if prompt:
        await generate_canvas_cover(canvas_id, prompt)
        return

    db_prompt = await db_service.get_canvas_first_user_prompt(canvas_id)
    if db_prompt:
        await generate_canvas_cover(canvas_id, db_prompt)


def schedule_canvas_cover_generation(
    canvas_id: str,
    messages: Optional[List[Dict[str, Any]]] = None,
) -> None:
    prompt = extract_prompt_from_messages(messages or [])
    asyncio.create_task(_generate_cover_with_fallback(canvas_id, prompt))


def schedule_missing_canvas_covers(canvases: List[Dict[str, Any]]) -> None:
    for canvas in canvases:
        if canvas.get("thumbnail"):
            continue
        schedule_canvas_cover_generation(canvas["id"])
