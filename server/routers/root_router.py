from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
import os
from models.tool_model import ToolInfoJson
from services.tool_service import tool_service
from services.config_service import config_service
from services.db_service import db_service
from services.model_list_cache import (
    get_cached_models,
    get_cached_ollama_models,
    get_cached_tools,
    set_cached_models,
    set_cached_ollama_models,
    set_cached_tools,
    should_log_ollama_failure,
)
from utils.http_client import HttpClient
from models.config_model import ModelInfo
from routers.auth_router import get_current_user_id

router = APIRouter(prefix="/api")


async def get_ollama_model_list(base_url: str) -> List[str]:
    cached = get_cached_ollama_models()
    if cached is not None:
        return cached

    try:
        timeout = httpx.Timeout(2.0, connect=1.0)
        async with HttpClient.create(timeout=timeout) as client:
            response = await client.get(f'{base_url.rstrip("/")}/api/tags')
            response.raise_for_status()
            data = response.json()
            models = [model['name'] for model in data.get('models', [])]
            set_cached_ollama_models(models, failed=False)
            return models
    except Exception as e:
        if should_log_ollama_failure():
            print(
                f"Ollama unavailable at {base_url}, skipping for 5 min: {e}"
            )
        set_cached_ollama_models([], failed=True)
        return []


async def get_comfyui_model_list(base_url: str) -> List[str]:
    """Get ComfyUI model list from object_info API"""
    try:
        timeout = httpx.Timeout(10.0)
        async with HttpClient.create(timeout=timeout) as client:
            response = await client.get(f"{base_url}/api/object_info")
            if response.status_code == 200:
                data = response.json()
                # Extract models from CheckpointLoaderSimple node
                models = data.get('CheckpointLoaderSimple', {}).get(
                    'input', {}).get('required', {}).get('ckpt_name', [[]])[0]
                return models if isinstance(models, list) else []  # type: ignore
            else:
                print(f"ComfyUI server returned status {response.status_code}")
                return []
    except Exception as e:
        print(f"Error querying ComfyUI: {e}")
        return []

# List all LLM models
@router.get("/list_models")
async def get_models() -> list[ModelInfo]:
    cached = get_cached_models()
    if cached is not None:
        return cached

    config = config_service.get_config()
    res: List[ModelInfo] = []

    # Handle Ollama models separately
    ollama_url = config.get('ollama', {}).get(
        'url', os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
    # Add Ollama models if URL is available
    if ollama_url and ollama_url.strip():
        ollama_models = await get_ollama_model_list(ollama_url)
        for ollama_model in ollama_models:
            res.append({
                'provider': 'ollama',
                'model': ollama_model,
                'url': ollama_url,
                'type': 'text'
            })

    for provider in config.keys():
        if provider in ['ollama']:
            continue

        provider_config = config[provider]
        provider_url = provider_config.get('url', '').strip()
        provider_api_key = provider_config.get('api_key', '').strip()

        # Skip provider if URL is empty or API key is empty
        if not provider_url or not provider_api_key:
            continue

        models = provider_config.get('models', {})
        for model_name in models:
            model = models[model_name]
            model_type = model.get('type', 'text')
            # Only return text models
            if model_type == 'text':
                res.append({
                    'provider': provider,
                    'model': model_name,
                    'url': provider_url,
                    'type': model_type
                })
    set_cached_models(res)
    return res


@router.get("/list_tools")
async def list_tools() -> list[ToolInfoJson]:
    cached = get_cached_tools()
    if cached is not None:
        return cached

    config = config_service.get_config()
    res: list[ToolInfoJson] = []
    for tool_id, tool_info in tool_service.tools.items():
        if tool_info.get('provider') == 'system':
            continue
        provider = tool_info['provider']
        provider_api_key = config[provider].get('api_key', '').strip()
        if provider != 'comfyui' and not provider_api_key:
            continue
        res.append({
            'id': tool_id,
            'provider': tool_info.get('provider', ''),
            'type': tool_info.get('type', ''),
            'display_name': tool_info.get('display_name', ''),
        })

    set_cached_tools(res)
    return res


@router.get("/list_chat_sessions")
async def list_chat_sessions(
    canvas_id: str = None, user_id: str = Depends(get_current_user_id)
):
    return await db_service.list_sessions(canvas_id, user_id=user_id)


@router.get("/chat_session/{session_id}")
async def get_chat_session(
    session_id: str, user_id: str = Depends(get_current_user_id)
):
    if not await db_service.user_owns_session(session_id, user_id):
        # 新建会话可能尚未写入时，允许空历史（归属会在首条消息创建时绑定画布）
        owner = await db_service.get_session_owner(session_id)
        if owner is not None:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        return []
    return await db_service.get_chat_history(session_id)


@router.post("/chat_session/{session_id}/rename")
async def rename_chat_session(
    session_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    if not await db_service.user_owns_session(session_id, user_id):
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    data = await request.json()
    title = data.get("title")
    await db_service.update_session_title(session_id, title)
    return {"session_id": session_id, "title": title}
