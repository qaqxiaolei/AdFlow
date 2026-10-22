import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from services.open_generate_service import (
    create_task,
    get_task,
    normalize_mode,
    normalize_ratio,
    public_task_view,
    save_reference_images,
)

router = APIRouter(prefix="/api/open", tags=["open"])


class GenerateBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt: str = ""
    input: str = ""
    mode: str = ""
    generation_mode: str = ""
    quantity: int = 1
    aspect_ratio: Optional[str] = None
    image: Any = None
    images: Any = None


def _public_base(request: Request) -> str:
    configured = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    hostname = host.split(":")[0]
    if host and hostname not in ("127.0.0.1", "localhost"):
        return f"{proto}://{host}".rstrip("/")
    return "https://adflow.chat"


@router.post("/generate")
async def generate(
    body: GenerateBody,
    request: Request,
):
    """提交图像或视频生成任务，立刻返回 task_id。"""
    prompt = (body.prompt or body.input or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt 不能为空")
    if len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="prompt 过长")
    try:
        quantity = int(body.quantity)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="quantity 只能是 1 或 2")
    if quantity not in (1, 2):
        raise HTTPException(status_code=400, detail="quantity 只能是 1 或 2")
    try:
        mode = normalize_mode(body.mode, body.generation_mode)
        aspect_ratio = normalize_ratio(body.aspect_ratio, mode)
        reference_images = await save_reference_images(body.image, body.images)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        task = await create_task(
            prompt=prompt,
            mode=mode,
            quantity=quantity,
            aspect_ratio=aspect_ratio,
            public_base=_public_base(request),
            reference_images=reference_images,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    return task


@router.get("/tasks/{task_id}")
async def get_generate_task(task_id: str):
    """查询生成任务。status 为 succeeded 时 videos / images 里是可访问地址。"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return public_task_view(task)
