from models.tool_model import ToolInfoJson
from services.db_service import db_service
from .StreamProcessor import StreamProcessor
from .agent_manager import AgentManager
from .agent_cache import agent_cache
from services.performance_monitor import PerformanceMonitor
import traceback
from utils.http_client import HttpClient
from langgraph_swarm import create_swarm  # type: ignore
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from services.websocket_service import send_to_websocket  # type: ignore
from services.config_service import config_service
from typing import Optional, List, Dict, Any, cast
from typing_extensions import TypedDict
from models.config_model import ModelInfo
from .chat_history_fix import fix_openai_chat_history


class ContextInfo(TypedDict):
    """Context information passed to tools"""
    canvas_id: str
    session_id: str
    model_info: Dict[str, List[ModelInfo]]
    user_prompt: str


def _extract_last_user_prompt(messages: List[Dict[str, Any]]) -> str:
    """提取最近一条用户消息，供工具在缺少 prompt 时回退使用。"""
    for msg in reversed(messages):
        if msg.get('role') != 'user':
            continue

        content = msg.get('content', '')
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            texts: List[str] = []
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    text = part.get('text', '')
                    if isinstance(text, str) and text.strip():
                        texts.append(text)
            return '\n'.join(texts)

    return ''


async def langgraph_multi_agent(
    messages: List[Dict[str, Any]],
    canvas_id: str,
    session_id: str,
    text_model: ModelInfo,
    tool_list: List[ToolInfoJson],
    system_prompt: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """多智能体处理函数

    Args:
        messages: 消息历史
        canvas_id: 画布ID
        session_id: 会话ID
        text_model: 文本模型配置
        tool_list: 工具模型配置列表（图像或视频模型）
        system_prompt: 系统提示词
    """
    monitor = PerformanceMonitor()
    try:
        # 0. 修复消息历史
        monitor.start('fix_history')
        fixed_messages = fix_openai_chat_history(messages)
        monitor.end('fix_history')

        # 1. 尝试从缓存获取模型实例
        monitor.start('model_create')
        text_model_instance = agent_cache.get_model(text_model)
        if text_model_instance:
            print('✅ 使用缓存的模型实例')
        else:
            text_model_instance = _create_text_model(text_model)
            agent_cache.set_model(text_model, text_model_instance)
            print('🚀 创建新模型实例并缓存')
        monitor.end('model_create')

        # 2. 尝试从缓存获取智能体
        monitor.start('agent_create')
        agents = agent_cache.get_agents(text_model, tool_list)
        if agents:
            print('✅ 使用缓存的智能体')
        else:
            agents = AgentManager.create_agents(
                text_model_instance,
                tool_list,
                system_prompt or ""
            )
            agent_cache.set_agents(text_model, tool_list, agents)
            print('🚀 创建新智能体并缓存')
        monitor.end('agent_create')

        agent_names = [agent.name for agent in agents]
        last_agent = AgentManager.get_last_active_agent(
            fixed_messages, agent_names)

        # 3. 创建智能体群组（Swarm无法缓存，因为它包含状态）
        monitor.start('swarm_create')
        swarm = create_swarm(
            agents=agents,
            default_active_agent=last_agent if last_agent else agent_names[0]
        )
        monitor.end('swarm_create')

        # 5. 创建上下文
        user_prompt = _extract_last_user_prompt(fixed_messages)
        context = {
            'recursion_limit': 50,
            'configurable': {
                'canvas_id': canvas_id,
                'session_id': session_id,
                'tool_list': tool_list,
                'user_prompt': user_prompt,
                'user_id': user_id,
            },
        }

        # 6. 流处理
        processor = StreamProcessor(
            session_id, db_service, send_to_websocket)  # type: ignore
        await processor.process_stream(swarm, fixed_messages, context)

        monitor.log_timings(session_id)

    except Exception as e:
        monitor.log_timings(session_id)
        await _handle_error(e, session_id)


def _create_text_model(text_model: ModelInfo) -> Any:
    """创建语言模型实例"""
    model = text_model.get('model')
    provider = text_model.get('provider')
    url = text_model.get('url')
    api_key = config_service.app_config.get(  # type: ignore
        provider, {}).get("api_key", "")

    # TODO: Verify if max token is working
    # max_tokens = text_model.get('max_tokens', 8148)

    if provider == 'ollama':
        return ChatOllama(
            model=model,
            base_url=url,
        )
    else:
        # Create httpx client with SSL configuration for ChatOpenAI
        http_client = HttpClient.create_sync_client()
        http_async_client = HttpClient.create_async_client()
        return ChatOpenAI(
            model=model,
            api_key=api_key,  # type: ignore
            timeout=300,
            base_url=url,
            temperature=0,
            # max_tokens=max_tokens, # TODO: 暂时注释掉有问题的参数
            http_client=http_client,
            http_async_client=http_async_client
        )


async def _handle_error(error: Exception, session_id: str) -> None:
    """处理错误"""
    print('Error in langgraph_agent', error)
    tb_str = traceback.format_exc()
    print(f"Full traceback:\n{tb_str}")
    traceback.print_exc()

    await send_to_websocket(session_id, cast(Dict[str, Any], {
        'type': 'error',
        'error': str(error)
    }))
