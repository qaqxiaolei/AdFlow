"""
视频生成核心模块
包含跨不同 provider 的视频生成主调度逻辑
"""

import traceback
from typing import List, cast, Optional, Any
from models.config_model import ModelInfo
from ..video_providers.video_base_provider import (
    resolve_video_provider,
    VideoProviderBase,
)
# 导入所有 provider 以确保自动注册（请勿删除这些 import）
from ..video_providers.volces_provider import VolcesVideoProvider  # type: ignore
from ..video_providers.agnes_provider import AgnesVideoProvider  # type: ignore
from .video_canvas_utils import (
    send_video_start_notification,
    send_video_error_notification,
    send_tool_call_progress,
    process_video_result,
)

async def generate_video_with_provider(
    prompt: str,
    resolution: str,
    duration: int,
    aspect_ratio: str,
    model: str,
    tool_call_id: str,
    config: Any,
    input_images: Optional[list[str]] = None,
    camera_fixed: bool = True,
    ratio: str = "",
    notify_on_error: bool = True,
    provider: Optional[str] = None,
    **kwargs: Any
) -> str:
    """
    通用视频生成函数，支持不同模型与 provider
    Args:
        prompt: 视频生成提示词
        resolution: 视频分辨率（480p、1080p）
        duration: 视频时长（秒，如 5、10）
        aspect_ratio: 视频宽高比（1:1、16:9、4:3、21:9）
        model: 模型标识（如 'doubao-seedance-1-0-pro'）
        tool_call_id: 工具调用 ID
        config: LangGraph 注入的运行时配置，含 canvas_id、session_id、model_info 等
        input_images: 可选的参考图/首帧图片列表
        camera_fixed: 是否固定镜头
        ratio: 视频比例，与 aspect_ratio 相同；未提供时使用 aspect_ratio
    Returns:
        str: 生成结果消息
    """
    model_name = model.split(
        # 部分模型名含 "/"，如 "openai/gpt-image-1"，需取最后一段
        '/')[-1]
    print(f'🛠️ Video Generation {model_name} tool_call_id', tool_call_id)
    ctx = config.get('configurable', {})
    canvas_id = ctx.get('canvas_id', '')
    session_id = ctx.get('session_id', '')
    print(f'🛠️ canvas_id {canvas_id} session_id {session_id}')
    # 将 tool_call_id 注入上下文
    ctx['tool_call_id'] = tool_call_id
    try:
        # 确定使用哪个 provider
        model_info_list: List[ModelInfo] = cast(
            List[ModelInfo], ctx.get('model_info', {}).get(model_name, []))
        tool_list = cast(List[ModelInfo], ctx.get('tool_list', []))
        provider_name = resolve_video_provider(
            model_name=model_name,
            model_info_list=model_info_list if model_info_list else None,
            tool_list=tool_list if tool_list else None,
            explicit_provider=provider,
        )
        print(f"🎥 Using provider: {provider_name} for {model_name}")
        # 创建 provider 实例
        provider_instance = VideoProviderBase.create_provider(provider_name)
        # 发送开始通知
        await send_video_start_notification(
            session_id,
            f"Starting video generation using {model_name} via {provider_name}..."
        )
        await send_tool_call_progress(
            session_id, tool_call_id, "正在提交视频生成任务..."
        )
        # 为 provider 准备输入图片
        processed_input_images = None
        if input_images:
            # 部分 provider 可能需要不同的图片处理方式，目前原样传递
            processed_input_images = input_images
        # 调用所选 provider 生成视频
        video_url = await provider_instance.generate(
            prompt=prompt,
            model=model,
            resolution=resolution,
            duration=duration,
            aspect_ratio=aspect_ratio,
            input_images=processed_input_images,
            camera_fixed=camera_fixed,
            session_id=session_id,
            tool_call_id=tool_call_id,
            **kwargs
        )
        # 处理视频结果（保存、更新画布、通知前端）
        return await process_video_result(
            video_url=video_url,
            session_id=session_id,
            canvas_id=canvas_id,
            provider_name=f"{model_name} ({provider_name})",
            tool_call_id=tool_call_id,
        )
    except Exception as e:
        error_message = str(e)
        print(f"🎥 Error generating video with {model_name}: {error_message}")
        print(f"🎥 Full error traceback:")
        traceback.print_exc()
        print(f"🎥 Context info - canvas_id: {canvas_id}, session_id: {session_id}")
        print(f"🎥 Generation params - prompt: {prompt[:100]}..., resolution: {resolution}, duration: {duration}, aspect_ratio: {aspect_ratio}")
        # 批量生成时部分失败由工具结果汇总告知，避免重复弹红色错误
        await send_video_error_notification(
            session_id,
            error_message,
            notify_user=notify_on_error,
        )
        # 重新抛出异常，供上层正确处理
        raise Exception(
            f"{model_name} video generation failed: {error_message}")
