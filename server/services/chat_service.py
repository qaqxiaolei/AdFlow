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
    # 从传入的数据中提取字段
    messages: List[Dict[str, Any]] = data.get('messages', [])
    session_id: str = data.get('session_id', '')
    canvas_id: str = data.get('canvas_id', '')
    text_model: ModelInfo = data.get('text_model', {})
    tool_list: List[ToolInfoJson] = data.get('tool_list', [])
    print('👇 聊天服务已接收到前端传过来的工具列表', tool_list)
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
        print('👇 聊天服务已添加搜索视频工具到工具列表')
    # 从数据库或配置文件里读取系统提示词
    system_prompt: Optional[str] = data.get('system_prompt')
    # 如果只有一条消息，创建一个新的聊天会话
    if len(messages) == 1:
        # 创建新的聊天会话
        prompt = messages[0].get('content', '')
        # 更好的方式来确定何时创建新的聊天会话。
        await db_service.create_chat_session(session_id, text_model.get('model'), text_model.get('provider'), canvas_id, (prompt[:200] if isinstance(prompt, str) else ''))
    await db_service.create_message(session_id, messages[-1].get('role', 'user'), json.dumps(messages[-1])) if len(messages) > 0 else None
    # 创建并启动 langgraph_agent 任务来处理聊天请求
    task = asyncio.create_task(langgraph_multi_agent(
        messages, canvas_id, session_id, text_model, tool_list, system_prompt))
    # 将任务注册到 stream_tasks 中（用于可能的取消）
    add_stream_task(session_id, task)
    try:
        # 等待 langgraph_agent 任务完成
        await task
    except asyncio.exceptions.CancelledError:
        print(f"🛑 会话 {session_id} 在流式处理期间被取消")
    finally:
        # 在任务完成/取消后，从 stream_tasks 中移除任务
        remove_stream_task(session_id)
        # 通过 WebSocket 通知前端聊天处理已完成
        await send_to_websocket(session_id, {
            'type': 'done'
        })