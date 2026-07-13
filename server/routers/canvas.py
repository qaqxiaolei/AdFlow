from fastapi import APIRouter, Request
#from routers.agent import chat
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
import asyncio
import json

router = APIRouter(prefix="/api/canvas")

@router.get("/list")
async def list_canvases():
    canvases = await db_service.list_canvases()
    schedule_missing_canvas_covers(canvases)
    schedule_missing_canvas_names(canvases)
    return canvases

@router.post("/create")
async def create_canvas(request: Request):
    data = await request.json()
    id = data.get('canvas_id')
    session_id = data.get('session_id')
    messages = data.get('messages', [])
    prompt = extract_prompt_from_messages(messages)
    fallback_name = data.get('name') or "未命名"
    name = build_canvas_name_from_prompt(prompt) if prompt else fallback_name
    asyncio.create_task(handle_chat(data))
    await db_service.create_canvas(id, name, session_id)
    await db_service.prune_canvases()
    schedule_canvas_cover_generation(id, messages)
    if name in DEFAULT_CANVAS_NAMES:
        schedule_canvas_name_update(id, messages, session_id)
    return {"id": id }

@router.get("/{id}")
async def get_canvas(id: str):
    return await db_service.get_canvas_data(id)

@router.post("/{id}/save")
async def save_canvas(id: str, request: Request):
    payload = await request.json()
    data_str = json.dumps(payload['data'])
    await db_service.save_canvas_data(id, data_str, payload['thumbnail'])
    return {"id": id }

@router.post("/{id}/rename")
async def rename_canvas(id: str, request: Request):
    data = await request.json()
    name = data.get('name')
    await db_service.rename_canvas(id, name)
    return {"id": id }

@router.delete("/{id}/delete")
async def delete_canvas(id: str):
    await db_service.delete_canvas(id)
    return {"id": id }