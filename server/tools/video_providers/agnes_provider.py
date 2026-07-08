"""
Agnes AI 视频生成提供者

使用 Agnes AI 视频模型生成视频，支持模型自动降级和预校验机制。
"""

import json
import traceback
import asyncio
from typing import Optional, Dict, Any, List
import httpx

from .video_base_provider import VideoProviderBase
from utils.http_client import HttpClient
from services.config_service import config_service
from ..agnes_api_routes import (
    AGNES_VIDEO_API_ROUTE,
    AGNES_VIDEO_POLL_ROUTE,
    AGNES_AGNESAPI_POLL_ROUTE,
    build_video_api_url,
    get_api_root,
)
from ..agnes_model_config import (
    AGNES_VIDEO_MODELS,
    AGNES_VIDEO_MODEL_DEFAULT,
    is_valid_video_model,
)


class AgnesVideoProvider(VideoProviderBase, provider_name="agnes"):
    """Agnes AI video generation provider implementation using httpx"""

    def __init__(self):
        config = config_service.app_config.get('agnes', {})
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("url", "").rstrip("/")

        if not self.api_key:
            raise ValueError("Agnes API key is not configured")
        if not self.base_url:
            raise ValueError("Agnes URL is not configured")

        self._validate_api_endpoint()

    def _validate_api_endpoint(self) -> None:
        """
        接口可用性检测：启动时预请求基础接口，提前拦截无效地址配置
        """
        async def check_endpoint():
            api_url = build_video_api_url(self.base_url)
            headers = self._build_headers()

            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                    response = await client.options(api_url, headers=headers)
                    if response.status_code == 404:
                        print(f"⚠️ [Agnes-Video] API 端点不可用: {api_url}")
                        print(f"⚠️ [Agnes-Video] 请核对 Agnes 服务接口路由配置")
                    else:
                        print(f"✅ [Agnes-Video] API 端点校验通过: {api_url}")
                        print(f"✅ [Agnes-Video] 可用模型列表: {AGNES_VIDEO_MODELS}")
            except Exception as e:
                print(f"⚠️ [Agnes-Video] API 端点检测失败: {e}")
                print(f"⚠️ [Agnes-Video] URL: {api_url}")

        try:
            asyncio.get_event_loop().create_task(check_endpoint())
        except Exception:
            pass

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _extract_video_url(self, poll_res: Dict[str, Any]) -> Optional[str]:
        for key in ("url", "video_url", "result_url", "remixed_from_video_id"):
            value = poll_res.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
        return None

    def _extract_error_info(self, response: httpx.Response) -> dict:
        """
        从响应中提取错误信息
        """
        error_info = {
            "status_code": response.status_code,
            "request_id": "",
            "error_code": "",
            "error_message": "",
        }

        try:
            error_data = response.json()
            error_info["error_code"] = error_data.get("error", {}).get("code", "")
            error_info["error_message"] = error_data.get("error", {}).get("message", "")
            
            error_message = error_info["error_message"]
            if "request id:" in error_message:
                request_id_start = error_message.find("request id:") + len("request id:")
                request_id_end = error_message.find(")", request_id_start)
                if request_id_end > request_id_start:
                    error_info["request_id"] = error_message[request_id_start:request_id_end].strip()
                else:
                    error_info["request_id"] = error_message[request_id_start:].strip()[:50]
        except Exception:
            error_info["error_message"] = response.text[:200]

        return error_info

    async def _poll_task_status(
        self,
        task_id: str,
        headers: Dict[str, str],
        video_id: Optional[str] = None,
    ) -> str:
        polling_url = f"{self.base_url}{AGNES_VIDEO_POLL_ROUTE.format(task_id=task_id)}"
        max_attempts = 60
        initial_interval = 2.0
        max_interval = 15.0

        print(f"🎥 [Agnes-Video] 轮询URL: {polling_url}")

        for attempt in range(max_attempts):
            print(f"🎥 [Agnes-Video] 轮询任务状态 {task_id} (尝试 {attempt+1})...")

            try:
                async with HttpClient.create(timeout=httpx.Timeout(30.0)) as client:
                    response = await client.get(polling_url, headers=headers)

                    if response.status_code == 429:
                        interval = min(initial_interval * (2 ** attempt), max_interval)
                        print(f"🎥 [Agnes-Video] 轮询限流，等待 {interval} 秒...")
                        await asyncio.sleep(interval)
                        continue

                    if response.status_code == 404:
                        print(f"🎥 [Agnes-Video] 轮询端点不存在: {polling_url}")
                        raise Exception("视频状态查询接口地址无效，请核对Agnes服务接口路由配置")

                    if response.status_code != 200:
                        error_text = response.text
                        raise Exception(f"获取任务状态失败: HTTP {response.status_code} - {error_text}")

                    try:
                        poll_res = response.json()
                    except Exception:
                        raise Exception(f"解析任务状态失败: {response.text}")

                    status = poll_res.get("status", None)

                    if status in ("succeeded", "completed"):
                        video_url = self._extract_video_url(poll_res)
                        if video_url:
                            await asyncio.sleep(3)
                            return video_url
                        raise Exception("生成成功但未找到视频链接")
                    elif status == "failed":
                        error_message = poll_res.get("error", f"任务失败: {status}")
                        raise Exception(f"视频生成失败: {error_message}")
                    elif status == "cancelled":
                        raise Exception("任务已取消")
                    elif status in ("pending", "processing", "running", "queued", "in_progress"):
                        interval = min(initial_interval * (1.5 ** attempt), max_interval)
                        print(f"🎥 [Agnes-Video] 任务 {task_id} 状态 {status}，下次轮询在 {interval:.1f}s 后")
                        await asyncio.sleep(interval)
                        continue
                    else:
                        raise Exception(f"未知任务状态: {status}")
            except Exception as e:
                if "Connection" in str(e) or "timeout" in str(e).lower():
                    interval = min(initial_interval * (2 ** attempt), max_interval)
                    print(f"🎥 [Agnes-Video] 轮询连接问题: {e}，{interval:.1f}s 后重试...")
                    await asyncio.sleep(interval)
                    continue
                raise

        raise Exception(f"视频生成超时，请稍后重试")

    async def generate(
        self,
        prompt: str,
        model: str,
        resolution: str = "480p",
        duration: int = 5,
        aspect_ratio: str = "16:9",
        input_images: Optional[List[str]] = None,
        camera_fixed: bool = True,
        **kwargs: Any
    ) -> str:
        # 【预校验机制】发起请求前检查模型是否在白名单中
        if not is_valid_video_model(model):
            raise ValueError(
                f"视频模型 '{model}' 不在可用白名单中。"
                f"可用视频模型: {AGNES_VIDEO_MODELS}"
            )

        try:
            api_url = build_video_api_url(self.base_url)
            headers = self._build_headers()

            print(f"🎥 [Agnes-Video] 请求URL: {api_url}")

            # 准备模型列表：优先使用指定模型，其次使用配置的备用模型
            models_to_try = [model]
            if model == AGNES_VIDEO_MODEL_DEFAULT:
                models_to_try.extend([m for m in AGNES_VIDEO_MODELS if m != model])

            print(f"🎥 [Agnes-Video] 准备尝试的模型列表: {models_to_try}")

            target_frames = duration * 24
            n = round((target_frames - 1) / 8)
            num_frames = max(9, 8 * n + 1)

            last_error = None
            request_id = ""

            for attempt_idx, current_model in enumerate(models_to_try):
                try:
                    payload = {
                        "model": current_model,
                        "prompt": prompt,
                        "num_frames": num_frames,
                        "aspect_ratio": aspect_ratio,
                        "ratio": aspect_ratio,
                    }

                    if input_images:
                        payload["input_images"] = input_images
                        payload["image_ref_strength"] = 0.85

                    print(f"🎥 [Agnes-Video] 开始视频生成 - 模型: {current_model} (尝试 {attempt_idx + 1}/{len(models_to_try)})")

                    max_retries = 2
                    retry_wait = 65

                    for inner_attempt in range(max_retries + 1):
                        print(f"🎥 [Agnes-Video] 视频生成尝试 {inner_attempt+1}/{max_retries+1}")

                        task_id = None
                        video_id = None

                        try:
                            async with HttpClient.create(timeout=httpx.Timeout(60.0)) as client:
                                response = await client.post(api_url, json=payload, headers=headers)

                                # 404错误捕获
                                if response.status_code == 404:
                                    print(f"🎥 [Agnes-Video] API 返回404: {response.text[:100]}")
                                    raise Exception("视频生成接口地址无效，请核对Agnes服务接口路由配置")

                                # 503错误处理（包含model_not_found）
                                if response.status_code == 503:
                                    error_info = self._extract_error_info(response)
                                    request_id = error_info["request_id"]
                                    print(f"🎥 [Agnes-Video] API 返回503 - 请求ID: {request_id}, 错误码: {error_info['error_code']}, 错误信息: {error_info['error_message']}")

                                    if error_info["error_code"] == "model_not_found":
                                        # 【模型降级逻辑】model_not_found时尝试备用模型
                                        if attempt_idx < len(models_to_try) - 1:
                                            next_model = models_to_try[attempt_idx + 1]
                                            print(f"🎥 [Agnes-Video] 模型 '{current_model}' 通道不可用，自动降级到备用模型 '{next_model}'")
                                            last_error = error_info
                                            break

                                        # 所有模型都不可用，抛出清晰错误
                                        raise Exception(
                                            f"视频模型通道不可用。所有配置的视频模型均无法访问。"
                                            f"尝试过的模型: {models_to_try}。"
                                            f"请求ID: {request_id}。"
                                            f"请联系服务商开通视频生成权限或切换可用视频模型。"
                                        )

                                    raise Exception(f"Agnes API 服务不可用: {error_info['error_message']}")

                                if response.status_code == 200:
                                    try:
                                        result = response.json()
                                    except Exception:
                                        raise Exception(f"解析响应失败: {response.text}")

                                    task_id = result.get("task_id", None) or result.get("id", None)
                                    video_id = result.get("video_id", None)

                                    if not task_id and not video_id:
                                        print("🎥 [Agnes-Video] 创建视频任务失败:", result)
                                        raise Exception("创建视频任务失败，请稍后重试")

                                    print(
                                        f"🎥 [Agnes-Video] 视频任务创建成功, "
                                        f"任务ID: {task_id}, 视频ID: {video_id}"
                                    )

                                elif response.status_code == 429:
                                    print(f"🎥 [Agnes-Video] 限流 (尝试 {inner_attempt+1}/{max_retries})")
                                    raise Exception("RATE_LIMIT_ERROR")

                                elif response.status_code == 503:
                                    print(f"🎥 [Agnes-Video] 服务不可用 (尝试 {inner_attempt+1}/{max_retries})")
                                    raise Exception("SERVICE_UNAVAILABLE_ERROR")

                                else:
                                    try:
                                        error_data = response.json()
                                        error_message = error_data.get("message", f"HTTP {response.status_code}")
                                    except Exception:
                                        error_message = f"HTTP {response.status_code}: {response.text}"

                                    if "rate_limit" in error_message.lower() or "ServiceUnavailable" in error_message:
                                        print(f"🎥 [Agnes-Video] 需要重试 (尝试 {inner_attempt+1}/{max_retries}): {error_message}")
                                        raise Exception("RETRY_REQUIRED_ERROR")

                                    if response.status_code == 400:
                                        raise Exception(f"视频参数错误: {error_message}")

                                    raise Exception(f"创建视频任务失败: {error_message}")

                        except Exception as e:
                            exc_msg = str(e)
                            if exc_msg in ("RATE_LIMIT_ERROR", "SERVICE_UNAVAILABLE_ERROR", "RETRY_REQUIRED_ERROR") and inner_attempt < max_retries:
                                print(f"🎥 [Agnes-Video] 将在 {retry_wait} 秒后重试...")
                                await asyncio.sleep(retry_wait)
                                continue
                            elif ("Connection" in exc_msg or "timeout" in exc_msg.lower()) and inner_attempt < max_retries:
                                print(f"🎥 [Agnes-Video] 连接问题: {exc_msg}, {retry_wait} 秒后重试...")
                                await asyncio.sleep(retry_wait)
                                continue
                            else:
                                raise

                    if task_id or video_id:
                        resolved_task_id = task_id or video_id or ""
                        video_url = await self._poll_task_status(
                            resolved_task_id,
                            headers,
                            video_id=video_id,
                        )
                        print(f"🎥 [Agnes-Video] 视频生成成功 - 模型: {current_model}, 视频URL: {video_url}")
                        return video_url

                    # 如果是因为model_not_found而break，继续尝试下一个模型
                    if last_error and last_error.get("error_code") == "model_not_found":
                        continue

                    raise Exception("视频生成请求过于频繁，请等待1分钟后再试")

                except Exception as e:
                    error_msg = str(e)
                    if "rate_limit" in error_msg.lower() or "429" in error_msg or error_msg == "RATE_LIMIT_ERROR":
                        raise Exception("视频生成请求过于频繁，请等待1分钟后再试")
                    elif "Connection" in error_msg:
                        raise Exception("网络连接中断，请重试")
                    elif "timeout" in error_msg.lower():
                        raise Exception("视频生成超时，请稍后重试")
                    elif error_msg in ("SERVICE_UNAVAILABLE_ERROR", "RETRY_REQUIRED_ERROR"):
                        raise Exception("服务暂时不可用，请稍后重试")
                    print(f"🎥 [Agnes-Video] 视频生成失败 (模型: {current_model}, 尝试 {attempt_idx + 1}/{len(models_to_try)}): {error_msg}")
                    traceback.print_exc()

                    # 如果是所有模型都尝试过了，抛出最终错误
                    if attempt_idx >= len(models_to_try) - 1:
                        raise e

                    # 否则继续尝试下一个模型
                    last_error = e
                    continue

            if last_error:
                raise last_error
            raise Exception("视频生成失败")

        except Exception as e:
            error_msg = str(e)
            print(f"🎥 [Agnes-Video] 视频生成最终失败: {error_msg}")
            traceback.print_exc()
            raise


__all__ = ["AgnesVideoProvider"]
