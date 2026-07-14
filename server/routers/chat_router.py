# server/routers/chat_router.py
from fastapi import APIRouter, Depends, HTTPException, Request
from services.chat_service import handle_chat
from services.magic_service import handle_magic
from services.stream_service import get_stream_task, get_chat_status
from services.db_service import db_service
from routers.auth_router import get_current_user_id
from typing import Dict

router = APIRouter(prefix="/api")


@router.post("/chat")
async def chat(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    处理聊天请求的接口。
    接收客户端发来的 JSON 数据，交给聊天服务处理，并返回成功状态。
    """
    data = await request.json()
    data["user_id"] = user_id

    canvas_id = data.get("canvas_id")
    if canvas_id and not await db_service.user_owns_canvas(canvas_id, user_id):
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    session_id = data.get("session_id")
    if session_id:
        owner = await db_service.get_session_owner(session_id)
        if owner is not None and owner != user_id:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")

    await handle_chat(data)
    return {"status": "done"}


@router.get("/chat/status/{session_id}")
async def chat_status(
    session_id: str, user_id: str = Depends(get_current_user_id)
):
    """
    查询指定会话是否仍在生成，以及最后一次进度文本（用于页面刷新后恢复 UI）。
    """
    owner = await db_service.get_session_owner(session_id)
    if owner is not None and owner != user_id:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return get_chat_status(session_id)


@router.post("/cancel/{session_id}")
async def cancel_chat(
    session_id: str, user_id: str = Depends(get_current_user_id)
):
    """
    取消指定会话正在进行的流式任务。
    """
    owner = await db_service.get_session_owner(session_id)
    if owner is not None and owner != user_id:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    task = get_stream_task(session_id)
    if task and not task.done():
        task.cancel()
        return {"status": "cancelled"}
    return {"status": "not_found_or_done"}


@router.post("/magic")
async def magic(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    处理 Magic 生成请求的接口。
    """
    data = await request.json()
    data["user_id"] = user_id
    canvas_id = data.get("canvas_id")
    if canvas_id and not await db_service.user_owns_canvas(canvas_id, user_id):
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    await handle_magic(data)
    return {"status": "done"}


@router.post("/magic/cancel/{session_id}")
async def cancel_magic(
    session_id: str, user_id: str = Depends(get_current_user_id)
) -> Dict[str, str]:
    """
    取消指定会话正在进行的 Magic 生成任务。
    """
    owner = await db_service.get_session_owner(session_id)
    if owner is not None and owner != user_id:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    task = get_stream_task(session_id)
    if task and not task.done():
        task.cancel()
        return {"status": "cancelled"}
    return {"status": "not_found_or_done"}
