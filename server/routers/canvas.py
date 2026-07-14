from fastapi import APIRouter, Depends, HTTPException, Request
from services.chat_service import handle_chat
from services.db_service import db_service
from services.canvas_cover_service import (
    schedule_canvas_cover_generation,
    schedule_missing_canvas_covers,
    extract_prompt_from_messages,
    build_canvas_name_from_prompt,
    schedule_canvas_name_update,
    schedule_missing_canvas_names,
    DEFAULT_CANVAS_NAMES,
)
from routers.auth_router import get_current_user_id
import asyncio
import json

router = APIRouter(prefix="/api/canvas")


@router.get("/list")
async def list_canvases(user_id: str = Depends(get_current_user_id)):
    canvases = await db_service.list_canvases(user_id)
    schedule_missing_canvas_covers(canvases)
    schedule_missing_canvas_names(canvases)
    return canvases


@router.post("/create")
async def create_canvas(
    request: Request, user_id: str = Depends(get_current_user_id)
):
    data = await request.json()
    id = data.get("canvas_id")
    session_id = data.get("session_id")
    messages = data.get("messages", [])
    prompt = extract_prompt_from_messages(messages)
    fallback_name = data.get("name") or "未命名"
    name = build_canvas_name_from_prompt(prompt) if prompt else fallback_name
    data["user_id"] = user_id
    await db_service.create_canvas(id, name, session_id, user_id=user_id)
    await db_service.prune_canvases(user_id)
    asyncio.create_task(handle_chat(data))
    schedule_canvas_cover_generation(id, messages)
    if name in DEFAULT_CANVAS_NAMES:
        schedule_canvas_name_update(id, messages, session_id)
    return {"id": id}


@router.get("/{id}")
async def get_canvas(id: str, user_id: str = Depends(get_current_user_id)):
    canvas = await db_service.get_canvas_data(id, user_id=user_id)
    if canvas is None:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    return canvas


@router.post("/{id}/save")
async def save_canvas(
    id: str, request: Request, user_id: str = Depends(get_current_user_id)
):
    payload = await request.json()
    data_str = json.dumps(payload["data"])
    ok = await db_service.save_canvas_data(
        id, data_str, payload["thumbnail"], user_id=user_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    return {"id": id}


@router.post("/{id}/rename")
async def rename_canvas(
    id: str, request: Request, user_id: str = Depends(get_current_user_id)
):
    data = await request.json()
    name = data.get("name")
    ok = await db_service.rename_canvas(id, name, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    return {"id": id}


@router.delete("/{id}/delete")
async def delete_canvas(id: str, user_id: str = Depends(get_current_user_id)):
    ok = await db_service.delete_canvas(id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    return {"id": id}
