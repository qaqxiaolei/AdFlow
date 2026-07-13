# server/routers/chat_router.py
from fastapi import APIRouter, Request
from services.chat_service import handle_chat
from services.magic_service import handle_magic
from services.stream_service import get_stream_task, get_chat_status
from typing import Dict

router = APIRouter(prefix="/api")

@router.post("/chat")
async def chat(request: Request):
    """
    处理聊天请求的接口。
    接收客户端发来的 JSON 数据，交给聊天服务处理，并返回成功状态。
    请求体：
        包含聊天数据的 JSON 对象。
    响应：
        {"status": "done"}
    """
    data = await request.json()
    await handle_chat(data)
    return {"status": "done"}

@router.get("/chat/status/{session_id}")
async def chat_status(session_id: str):
    """
    查询指定会话是否仍在生成，以及最后一次进度文本（用于页面刷新后恢复 UI）。
    """
    return get_chat_status(session_id)

@router.post("/cancel/{session_id}")
async def cancel_chat(session_id: str):
    """
    取消指定会话正在进行的流式任务。
    若任务存在且尚未完成，则将其取消。
    路径参数：
        session_id (str)：需要取消任务的会话 ID。
    响应：
        {"status": "cancelled"}：任务已取消。
        {"status": "not_found_or_done"}：任务不存在或已完成。
    """
    task = get_stream_task(session_id)
    if task and not task.done():
        task.cancel()
        return {"status": "cancelled"}
    return {"status": "not_found_or_done"}

@router.post("/magic")
async def magic(request: Request):
    """
    处理 Magic 生成请求的接口。
    接收客户端发来的 JSON 数据，交给 Magic 服务处理，并返回成功状态。
    请求体：
        包含 Magic 生成数据的 JSON 对象。
    响应：
        {"status": "done"}
    """
    data = await request.json()
    await handle_magic(data)
    return {"status": "done"}

@router.post("/magic/cancel/{session_id}")
async def cancel_magic(session_id: str) -> Dict[str, str]:
    """
    取消指定会话正在进行的 Magic 生成任务。
    若任务存在且尚未完成，则将其取消。
    路径参数：
        session_id (str)：需要取消任务的会话 ID。
    响应：
        {"status": "cancelled"}：任务已取消。
        {"status": "not_found_or_done"}：任务不存在或已完成。
    """
    task = get_stream_task(session_id)
    if task and not task.done():
        task.cancel()
        return {"status": "cancelled"}
    return {"status": "not_found_or_done"}
