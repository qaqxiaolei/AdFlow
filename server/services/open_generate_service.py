"""Coze 等外部调用的异步生成任务。

提交后立刻返回 task_id，生成仍走现有 LangGraph（planner → image_video_creator）。
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from nanoid import generate

from models.config_model import ModelInfo
from models.tool_model import ToolInfoJson
from services.config_service import FILES_DIR, USER_DATA_DIR, config_service
from services.db_service import db_service
from services.langgraph_service.agent_service import langgraph_multi_agent
from tools.utils.image_canvas_utils import generate_file_id
from tools.utils.image_utils import get_image_info_and_save

_TASKS_PATH = os.path.join(USER_DATA_DIR, "open_tasks.json")
_MAX_TASKS = 200
_MAX_RUNNING = 2
_VALID_RATIOS = {"1:1", "16:9", "9:16", "4:3", "21:9", "3:4", "3:2"}

_MARKDOWN_LINK = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
_FILE_URL = re.compile(
    r"(https?://[^\s)\"']+\.(?:mp4|webm|mov|png|jpe?g|webp)|/api/file/[^\s)\"']+\.(?:mp4|webm|mov|png|jpe?g|webp))",
    re.IGNORECASE,
)
_HIDE_TAG = re.compile(r"<hide_in_user_ui>.*?</hide_in_user_ui>", re.IGNORECASE | re.DOTALL)
_VIDEO_EXT = (".mp4", ".webm", ".mov")

_tasks: Dict[str, Dict[str, Any]] = {}
_lock = asyncio.Lock()
_loaded = False
_runners: Dict[str, asyncio.Task] = {}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    if not os.path.isfile(_TASKS_PATH):
        return
    try:
        with open(_TASKS_PATH, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception as exc:
        print(f"[open-api] 读取任务文件失败: {exc}")
        return
    if not isinstance(raw, list):
        return
    for item in raw:
        if not isinstance(item, dict) or not item.get("task_id"):
            continue
        if item.get("status") == "running":
            item["status"] = "failed"
            item["error"] = "服务已重启，请重新提交"
            item["updated_at"] = _now()
        _tasks[item["task_id"]] = item


def _save() -> None:
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    items = list(_tasks.values())
    items.sort(key=lambda item: item.get("created_at") or "")
    if len(items) > _MAX_TASKS:
        dropped = items[: len(items) - _MAX_TASKS]
        for item in dropped:
            _tasks.pop(item.get("task_id"), None)
        items = items[-_MAX_TASKS :]
    tmp = _TASKS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(items, handle, ensure_ascii=False)
    os.replace(tmp, _TASKS_PATH)


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    _load()
    task = _tasks.get(task_id)
    return dict(task) if task else None


def public_task_view(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "videos": task.get("videos") or [],
        "images": task.get("images") or [],
        "text": task.get("text") or "",
        "error": task.get("error"),
    }


async def create_task(
    prompt: str,
    mode: str,
    quantity: int,
    aspect_ratio: Optional[str],
    public_base: str,
    reference_images: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    _load()
    task_id = "ot_" + generate(size=12)
    task = {
        "task_id": task_id,
        "status": "running",
        "mode": mode,
        "quantity": quantity,
        "aspect_ratio": aspect_ratio,
        "prompt": prompt,
        "reference_images": reference_images or [],
        "public_base": public_base.rstrip("/"),
        "videos": [],
        "images": [],
        "text": "",
        "error": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    async with _lock:
        active = sum(1 for item in _tasks.values() if item.get("status") == "running")
        if active >= _MAX_RUNNING:
            raise RuntimeError("已有生成任务在执行，请稍后再试")
        _tasks[task_id] = task
        _save()
        _runners[task_id] = asyncio.create_task(_execute(task_id))
    return public_task_view(task)


async def _update(task_id: str, **fields: Any) -> None:
    async with _lock:
        task = _tasks.get(task_id)
        if not task:
            return
        task.update(fields)
        task["updated_at"] = _now()
        _save()


def pick_text_model() -> ModelInfo:
    config = config_service.get_config()
    agnes = config.get("agnes") or {}
    models = agnes.get("models") or {}
    url = (agnes.get("url") or "").strip()
    for name in ("agnes-2.5-flash", "agnes-2.0-flash"):
        meta = models.get(name) or {}
        if url and meta.get("type", "text") == "text":
            return {
                "provider": "agnes",
                "model": name,
                "url": url,
                "type": "text",
            }
    for provider, provider_config in config.items():
        if not isinstance(provider_config, dict):
            continue
        provider_url = (provider_config.get("url") or "").strip()
        api_key = (provider_config.get("api_key") or "").strip()
        if not provider_url or not api_key:
            continue
        for model_name, meta in (provider_config.get("models") or {}).items():
            if isinstance(meta, dict) and meta.get("type", "text") == "text":
                return {
                    "provider": provider,
                    "model": model_name,
                    "url": provider_url,
                    "type": "text",
                }
    raise RuntimeError("没有可用的文本模型，请先在服务端配置 Agnes")


def build_user_content(
    prompt: str,
    mode: str,
    quantity: int,
    aspect_ratio: Optional[str],
    reference_images: Optional[List[Dict[str, Any]]] = None,
) -> str:
    lines = [prompt.strip()]
    if aspect_ratio:
        lines.append(f"<aspect_ratio>{aspect_ratio}</aspect_ratio>")
    lines.append(f"<quantity>{quantity}</quantity>")
    lines.append(f"<generation_mode>{mode}</generation_mode>")
    images = reference_images or []
    if images:
        lines.append(f'<input_images count="{len(images)}">')
        for index, image in enumerate(images, start=1):
            lines.append(
                f'<image index="{index}" file_id="{image["file_id"]}" '
                f'width="{image["width"]}" height="{image["height"]}" />'
            )
        lines.append("</input_images>")
    return "\n".join(lines)


def _image_sources(value: Any) -> List[str]:
    """从 Coze 的 Image 变量里取出 URL 或 base64。没传图时返回空列表。"""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in ("null", "none", "{}", "[]"):
            return []
        return [text]
    if isinstance(value, dict):
        for key in ("url", "file_url", "image_url", "src", "uri", "data", "content"):
            inner = value.get(key)
            found = _image_sources(inner)
            if found:
                return found
        return []
    if isinstance(value, list):
        found: List[str] = []
        for item in value:
            found.extend(_image_sources(item))
        return found
    return []


async def save_reference_images(*values: Any) -> List[Dict[str, Any]]:
    """把 Coze 上传的参考图存到本地，供现有生成工具按 file_id 读取。"""
    sources: List[str] = []
    for value in values:
        sources.extend(_image_sources(value))
    if len(sources) > 3:
        raise ValueError("参考图最多 3 张")

    saved: List[Dict[str, Any]] = []
    os.makedirs(FILES_DIR, exist_ok=True)
    for source in sources:
        file_id = generate_file_id()
        path_without_ext = os.path.join(FILES_DIR, file_id)
        try:
            if source.startswith("data:") and ";base64," in source:
                payload = source.split(";base64,", 1)[1]
                _mime, width, height, extension = await get_image_info_and_save(
                    payload, path_without_ext, is_b64=True
                )
            else:
                _mime, width, height, extension = await get_image_info_and_save(
                    source, path_without_ext, is_b64=False
                )
        except Exception as exc:
            raise ValueError(f"参考图无法读取: {exc}") from exc
        saved.append({
            "file_id": f"{file_id}.{extension}",
            "width": width,
            "height": height,
        })
    return saved


def _message_text(message: Dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _absolute(url: str, public_base: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return public_base.rstrip("/") + url
    return url


def _is_video(url: str) -> bool:
    path = url.split("?", 1)[0].lower()
    return path.endswith(_VIDEO_EXT)


def extract_result(
    messages: List[Dict[str, Any]],
    public_base: str,
) -> tuple[List[str], List[str], str]:
    videos: List[str] = []
    images: List[str] = []
    seen = set()
    last_assistant = ""

    def push(url: str) -> None:
        absolute = _absolute(url.strip(), public_base)
        if not absolute or absolute in seen:
            return
        seen.add(absolute)
        if _is_video(absolute):
            videos.append(absolute)
        else:
            images.append(absolute)

    for message in messages:
        text = _message_text(message)
        if message.get("role") == "assistant" and text.strip():
            last_assistant = _HIDE_TAG.sub("", text).strip()
        for match in _MARKDOWN_LINK.findall(text):
            push(match)
        for match in _FILE_URL.findall(text):
            push(match)

    return videos, images, last_assistant


async def _execute(task_id: str) -> None:
    task = _tasks.get(task_id)
    if not task:
        return
    canvas_id = f"open_{task_id}"
    try:
        text_model = pick_text_model()
        title = (task["prompt"] or "开放接口")[:40]
        await db_service.create_canvas(canvas_id, title, task_id, user_id=None)
        await db_service.create_chat_session(
            task_id,
            text_model.get("model"),
            text_model.get("provider"),
            canvas_id,
            title,
        )
        tool_list: List[ToolInfoJson] = [
            {
                "id": "generate_image_by_agnes",
                "provider": "agnes",
                "type": "image",
                "display_name": "Agnes Image",
            },
            {
                "id": "generate_video_by_agnes",
                "provider": "volces",
                "type": "video",
                "display_name": "Seedance 2.0",
            },
        ]
        user_content = build_user_content(
            task["prompt"],
            task["mode"],
            task["quantity"],
            task.get("aspect_ratio"),
            task.get("reference_images"),
        )
        messages, error = await langgraph_multi_agent(
            [{"role": "user", "content": user_content}],
            canvas_id,
            task_id,
            text_model,
            tool_list,
            None,
            user_id=None,
        )
        videos, images, text = extract_result(messages, task.get("public_base") or "")
        reference_names = [
            item.get("file_id")
            for item in (task.get("reference_images") or [])
            if item.get("file_id")
        ]
        if reference_names:
            images = [
                url for url in images
                if not any(name in url for name in reference_names)
            ]
        if error and not videos and not images:
            await _update(task_id, status="failed", text=text, error=error, videos=[], images=[])
            return
        expected = videos if task["mode"] == "video" else images
        if not expected:
            await _update(
                task_id,
                status="failed",
                text=text,
                videos=videos,
                images=images,
                error=text or "模型没有返回文件",
            )
            return
        await _update(
            task_id,
            status="succeeded",
            text=text or "生成完成",
            videos=videos,
            images=images,
            error=None,
        )
    except Exception as exc:
        print(f"[open-api] 任务 {task_id} 失败: {exc}")
        await _update(task_id, status="failed", error=str(exc))
    finally:
        _runners.pop(task_id, None)


def normalize_mode(mode: str, generation_mode: str) -> str:
    value = (mode or generation_mode or "video").strip().lower()
    if value not in ("image", "video"):
        raise ValueError("mode 只能是 image 或 video")
    return value


def normalize_ratio(aspect_ratio: Optional[str], mode: str) -> Optional[str]:
    if aspect_ratio is None or str(aspect_ratio).strip() == "":
        return "9:16" if mode == "video" else None
    value = str(aspect_ratio).strip().replace("/", ":").replace(" ", "")
    if value not in _VALID_RATIOS:
        raise ValueError("aspect_ratio 不支持，可选 1:1、16:9、9:16、4:3、3:4、3:2、21:9")
    return value
