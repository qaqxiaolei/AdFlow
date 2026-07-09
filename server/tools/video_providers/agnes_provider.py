"""
Agnes AI 视频生成提供者

使用 Agnes AI 视频模型生成视频，支持模型自动降级和预校验机制。
"""

import traceback
import asyncio
import time
import random
from typing import Optional, Dict, Any, List
import httpx

from .video_base_provider import VideoProviderBase
from utils.http_client import HttpClient
from services.config_service import config_service
from ..agnes_api_routes import (
    AGNES_VIDEO_API_ROUTE,
    build_video_api_url,
    build_video_poll_url,
    build_video_alt_poll_url,
    build_agnesapi_poll_url,
)
from ..agnes_model_config import (
    AGNES_VIDEO_MODELS,
    AGNES_VIDEO_MODEL_DEFAULT,
    is_valid_video_model,
)

# Agnes 视频接口限流：约 1 次/分钟
VIDEO_CREATE_RATE_LIMIT_SECONDS = 62
# 单个视频轮询基础预算（秒），会按视频时长动态增加
VIDEO_POLL_BUDGET_BASE_SECONDS = 180
# 任务仍在 in_progress 时，超过预算后额外等待的宽限时间（秒）
VIDEO_POLL_GRACE_SECONDS = 120

VIDEO_SIZE_BY_RATIO = {
    ("9:16", "480p"): "480x854",
    ("9:16", "1080p"): "1080x1920",
    ("16:9", "480p"): "854x480",
    ("16:9", "1080p"): "1920x1080",
    ("1:1", "480p"): "480x480",
    ("1:1", "1080p"): "1080x1080",
    ("4:3", "480p"): "640x480",
    ("4:3", "1080p"): "1440x1080",
    ("3:4", "480p"): "480x640",
    ("3:4", "1080p"): "1080x1440",
    ("21:9", "480p"): "1120x480",
    ("21:9", "1080p"): "2520x1080",
}


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
        if not isinstance(poll_res, dict):
            return None

        for key in ("url", "video_url", "result_url", "download_url", "output_url"):
            value = poll_res.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value

        output = poll_res.get("output")
        if isinstance(output, dict):
            nested_url = self._extract_video_url(output)
            if nested_url:
                return nested_url
        elif isinstance(output, str) and output.startswith("http"):
            return output

        result = poll_res.get("result")
        if isinstance(result, dict):
            nested_url = self._extract_video_url(result)
            if nested_url:
                return nested_url

        data = poll_res.get("data")
        if isinstance(data, dict):
            nested_url = self._extract_video_url(data)
            if nested_url:
                return nested_url
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    nested_url = self._extract_video_url(item)
                    if nested_url:
                        return nested_url

        content = poll_res.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    nested_url = self._extract_video_url(item)
                    if nested_url:
                        return nested_url

        return None

    def _extract_poll_status(self, poll_res: Dict[str, Any]) -> Optional[str]:
        if not isinstance(poll_res, dict):
            return None

        for key in ("status", "state", "task_status"):
            value = poll_res.get(key)
            if isinstance(value, str):
                return value.lower()

        for nested_key in ("data", "output", "result"):
            nested = poll_res.get(nested_key)
            if isinstance(nested, dict):
                status = self._extract_poll_status(nested)
                if status:
                    return status

        # agnesapi 等接口可能直接返回视频 URL 而无 status 字段
        if self._extract_video_url(poll_res):
            return "succeeded"

        return None

    def _build_poll_urls(
        self,
        task_id: str,
        video_id: Optional[str],
        model_name: Optional[str],
    ) -> List[str]:
        urls: List[str] = []
        seen: set[str] = set()

        def add(url: str) -> None:
            if url and url not in seen:
                seen.add(url)
                urls.append(url)

        # 与 Apifox 一致：GET /agnesapi?video_id=xxx
        if video_id:
            add(build_agnesapi_poll_url(self.base_url, video_id))
        add(build_video_alt_poll_url(self.base_url, task_id))
        add(build_video_poll_url(self.base_url, task_id))
        return urls

    def _get_poll_interval(self, attempt: int) -> float:
        if attempt < 12:
            return 2.0
        if attempt < 30:
            return 3.0
        if attempt < 45:
            return 4.0
        return 5.0

    def _is_transient_network_error(self, error: Exception) -> bool:
        if isinstance(
            error,
            (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.ReadError,
                httpx.WriteError,
                httpx.NetworkError,
            ),
        ):
            return True

        error_text = f"{type(error).__name__} {error}".lower()
        return any(
            keyword in error_text
            for keyword in ("connection", "timeout", "timed out", "network")
        )

    def _get_poll_budget_seconds(self, duration: int) -> int:
        # 15s 视频在 Agnes 上常需 6-9 分钟；视频1本次用了 414s
        return max(600, VIDEO_POLL_BUDGET_BASE_SECONDS + duration * 30)

    def _max_poll_attempts(self, poll_budget: int) -> int:
        return max(60, poll_budget // 3)

    def _is_poll_in_progress(self, status: Optional[str]) -> bool:
        return status in (
            None,
            "pending",
            "processing",
            "running",
            "queued",
            "in_progress",
            "submitted",
            "created",
        )

    def _is_poll_succeeded(self, status: Optional[str]) -> bool:
        return status in ("succeeded", "completed", "success", "done", "finished")

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
        model_name: Optional[str] = None,
        duration: int = 10,
    ) -> str:
        polling_urls = self._build_poll_urls(task_id, video_id, model_name)
        poll_budget = self._get_poll_budget_seconds(duration)
        max_attempts = self._max_poll_attempts(poll_budget)
        poll_started_at = time.monotonic()

        print(
            f"🎥 [Agnes-Video] 轮询URL列表: {polling_urls}，"
            f"轮询预算: {poll_budget}s（时长 {duration}s）"
        )

        async with HttpClient.create(
            timeout=httpx.Timeout(30.0, connect=10.0)
        ) as client:
            for attempt in range(max_attempts):
                last_status: Optional[str] = None
                urls_to_try = polling_urls

                try:
                    for polling_url in urls_to_try:
                        try:
                            response = await client.get(polling_url, headers=headers)
                        except Exception as request_error:
                            if self._is_transient_network_error(request_error):
                                print(
                                    f"🎥 [Agnes-Video] 轮询请求超时，尝试下一个: "
                                    f"{polling_url} ({request_error})"
                                )
                                continue
                            raise

                        if response.status_code == 429:
                            await asyncio.sleep(self._get_poll_interval(attempt))
                            break

                        if response.status_code == 404:
                            continue

                        if response.status_code != 200:
                            continue

                        try:
                            poll_res = response.json()
                        except Exception:
                            continue

                        video_url = self._extract_video_url(poll_res)
                        if video_url:
                            elapsed = time.monotonic() - poll_started_at
                            print(
                                f"🎥 [Agnes-Video] 轮询成功 ({elapsed:.0f}s)，"
                                f"视频URL: {video_url}"
                            )
                            return video_url

                        status = self._extract_poll_status(poll_res)
                        last_status = status

                        if self._is_poll_succeeded(status):
                            raise Exception("生成成功但未找到视频链接")
                        if status == "failed":
                            error_message = poll_res.get("error", f"任务失败: {status}")
                            raise Exception(f"视频生成失败: {error_message}")
                        if status == "cancelled":
                            raise Exception("任务已取消")
                        if self._is_poll_in_progress(status):
                            if attempt % 4 == 0:
                                print(
                                    f"🎥 [Agnes-Video] [{polling_url}] "
                                    f"任务 {task_id} 状态 {status or '处理中'}"
                                )
                            continue

                    elapsed = time.monotonic() - poll_started_at
                    hard_limit = poll_budget + (
                        VIDEO_POLL_GRACE_SECONDS
                        if self._is_poll_in_progress(last_status)
                        else 0
                    )
                    if elapsed >= hard_limit:
                        raise Exception(
                            f"视频生成超时（已等待 {int(elapsed)} 秒，"
                            f"预算 {poll_budget} 秒），请稍后重试"
                        )

                    interval = self._get_poll_interval(attempt)
                    if attempt % 4 == 0:
                        print(
                            f"🎥 [Agnes-Video] 任务 {task_id} 仍在处理"
                            f"（最近状态: {last_status or '处理中'}），"
                            f"下次轮询在 {interval:.0f}s 后"
                        )
                    await asyncio.sleep(interval)
                except Exception as e:
                    if self._is_transient_network_error(e):
                        await asyncio.sleep(self._get_poll_interval(attempt))
                        continue
                    raise

        raise Exception(
            f"视频生成超时（预算 {poll_budget} 秒），请稍后重试"
        )

    def _resolve_video_size(self, aspect_ratio: str, resolution: str) -> Optional[str]:
        return VIDEO_SIZE_BY_RATIO.get((aspect_ratio, resolution))

    async def generate(
        self,
        prompt: str,
        model: str,
        resolution: str = "480p",
        duration: int = 5,
        aspect_ratio: str = "9:16",
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
                        "seed": random.randint(1, 2_147_483_647),
                    }

                    negative_prompt = kwargs.get("negative_prompt")
                    if negative_prompt:
                        payload["negative_prompt"] = negative_prompt

                    video_size = self._resolve_video_size(aspect_ratio, resolution)
                    if video_size:
                        payload["size"] = video_size

                    print(
                        f"🎥 [Agnes-Video] 视频参数: "
                        f"aspect_ratio={aspect_ratio}, size={video_size or 'auto'}"
                    )

                    if input_images:
                        payload["input_images"] = input_images
                        payload["image_ref_strength"] = 0.85

                    print(f"🎥 [Agnes-Video] 开始视频生成 - 模型: {current_model} (尝试 {attempt_idx + 1}/{len(models_to_try)})")

                    max_retries = 2
                    retry_wait = VIDEO_CREATE_RATE_LIMIT_SECONDS

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
                                    break

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
                            model_name=current_model,
                            duration=duration,
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
