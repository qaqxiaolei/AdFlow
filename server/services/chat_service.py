# services/chat_service.py

# Import necessary modules
import asyncio
import json
from typing import Dict, Any, List, Optional

# Import service modules
from models.tool_model import ToolInfoJson
from services.db_service import db_service
from services.langgraph_service import langgraph_multi_agent
from services.tool_service import tool_service
from services.websocket_service import send_to_websocket
from services.stream_service import add_stream_task, remove_stream_task
from models.config_model import ModelInfo


async def handle_chat(data: Dict[str, Any]) -> None:
    """
    处理前端发来的聊天请求

    Workflow:
    - 解析前端传过来的聊天请求数据包.
    - 可选注入系统提示词.
    - 保存聊天会话和消息到数据库中.
    - 启动 langgraph 代理任务来处理聊天请求.
    - 管理流任务生命周期 (添加, 移除).
    - 通过 WebSocket 通知前端流任务完成.

    Args:
        data (dict): 前端传过来的聊天请求数据包，包含以下字段：:
            - messages: 聊天消息列表
            - session_id: 唯一会话标识符
            - canvas_id: 画布标识符（上下文使用）
            - text_model: 文本模型配置信息
            - tool_list: 工具模型配置列表
    """
    # Extract fields from incoming data
    messages: List[Dict[str, Any]] = data.get('messages', [])
    session_id: str = data.get('session_id', '')
    canvas_id: str = data.get('canvas_id', '')
    text_model: ModelInfo = data.get('text_model', {})
    tool_list: List[ToolInfoJson] = data.get('tool_list', [])
    print('👇 chat_service got tool_list', tool_list)
    search_tool = tool_service.tools.get('search_video_by_platform')
    if search_tool:
        search_tool_info = {
            'id': 'search_video_by_platform',
            'name': 'search_video_by_platform',
            'display_name': search_tool.get('display_name', 'Video Search'),
            'type': search_tool.get('type', 'search'),
            'provider': search_tool.get('provider', 'system'),
        }
        tool_list.append(search_tool_info)
        print('👇 Added search_video_by_platform to tool_list')
    # TODO: save and fetch system prompt from db or settings config
    system_prompt: Optional[str] = data.get('system_prompt')
    # If there is only one message, create a new chat session
    if len(messages) == 1:
        # create new session
        prompt = messages[0].get('content', '')
        # TODO: Better way to determin when to create new chat session.
        await db_service.create_chat_session(session_id, text_model.get('model'), text_model.get('provider'), canvas_id, (prompt[:200] if isinstance(prompt, str) else ''))
    await db_service.create_message(session_id, messages[-1].get('role', 'user'), json.dumps(messages[-1])) if len(messages) > 0 else None
    # Create and start langgraph_agent task for chat processing
    task = asyncio.create_task(langgraph_multi_agent(
        messages, canvas_id, session_id, text_model, tool_list, system_prompt))
    # Register the task in stream_tasks (for possible cancellation)
    add_stream_task(session_id, task)
    try:
        # Await completion of the langgraph_agent task
        await task
    except asyncio.exceptions.CancelledError:
        print(f"🛑Session {session_id} cancelled during stream")
    finally:
        # Always remove the task from stream_tasks after completion/cancellation
        remove_stream_task(session_id)
        # Notify frontend WebSocket that chat processing is done
        await send_to_websocket(session_id, {
            'type': 'done'
        })
