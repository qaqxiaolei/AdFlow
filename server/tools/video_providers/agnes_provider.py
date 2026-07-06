import json
import traceback
import asyncio
from typing import Optional, Dict, Any, List
import httpx

from .video_base_provider import VideoProviderBase
from utils.http_client import HttpClient
from services.config_service import config_service


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

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _poll_task_status(self, task_id: str, headers: Dict[str, str]) -> str:
        polling_url = f"{self.base_url}/videos/{task_id}"
        max_attempts = 60
        initial_interval = 2.0
        max_interval = 15.0

        for attempt in range(max_attempts):
            print(f"🎥 Polling Agnes generation {task_id} (attempt {attempt+1})...")

            try:
                async with HttpClient.create(timeout=httpx.Timeout(30.0)) as client:
                    response = await client.get(polling_url, headers=headers)

                    if response.status_code == 429:
                        interval = min(initial_interval * (2 ** attempt), max_interval)
                        print(f"🎥 Polling rate limited, waiting {interval} seconds...")
                        await asyncio.sleep(interval)
                        continue

                    if response.status_code != 200:
                        error_text = response.text
                        raise Exception(f"获取任务状态失败: HTTP {response.status_code} - {error_text}")

                    try:
                        poll_res = response.json()
                    except Exception:
                        raise Exception(f"解析任务状态失败: {response.text}")

                    status = poll_res.get("status", None)

                    if status in ("succeeded", "completed"):
                        video_url = poll_res.get("url") or poll_res.get("video_url") or poll_res.get("result_url")
                        if video_url and isinstance(video_url, str):
                            return video_url
                        else:
                            raise Exception("生成成功但未找到视频链接")
                    elif status == "failed":
                        error_message = poll_res.get("error", f"任务失败: {status}")
                        raise Exception(f"视频生成失败: {error_message}")
                    elif status == "cancelled":
                        raise Exception("任务已取消")
                    elif status in ("pending", "processing", "running", "queued", "in_progress"):
                        interval = min(initial_interval * (1.5 ** attempt), max_interval)
                        print(f"🎥 Task {task_id} still {status}, next poll in {interval:.1f}s")
                        await asyncio.sleep(interval)
                        continue
                    else:
                        raise Exception(f"未知任务状态: {status}")
            except Exception as e:
                if "Connection" in str(e) or "timeout" in str(e).lower():
                    interval = min(initial_interval * (2 ** attempt), max_interval)
                    print(f"🎥 Polling connection issue: {e}, retrying in {interval:.1f}s...")
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
        try:
            api_url = f"{self.base_url}/videos"
            headers = self._build_headers()

            target_frames = duration * 24
            n = round((target_frames - 1) / 8)
            num_frames = max(9, 8 * n + 1)

            payload = {
                "model": model,
                "prompt": prompt,
                "num_frames": num_frames,
                "aspect_ratio": aspect_ratio,
            }

            if input_images:
                payload["input_images"] = input_images

            print(f"🎥 Starting Agnes video generation")

            max_retries = 2
            retry_wait = 65

            for attempt in range(max_retries + 1):
                print(f"🎥 Video generation attempt {attempt+1}/{max_retries+1}")

                task_id = None

                try:
                    async with HttpClient.create(timeout=httpx.Timeout(60.0)) as client:
                        response = await client.post(api_url, json=payload, headers=headers)

                        if response.status_code == 200:
                            try:
                                result = response.json()
                            except Exception:
                                raise Exception(f"解析响应失败: {response.text}")

                            task_id = result.get("task_id", None) or result.get("id", None)

                            if not task_id:
                                print("🎥 Failed to create Agnes video generation task:", result)
                                raise Exception("创建视频任务失败，请稍后重试")

                            print(f"🎥 Agnes video generation task created, task_id: {task_id}")

                        elif response.status_code == 429:
                            print(f"🎥 Agnes rate limit exceeded (attempt {attempt+1}/{max_retries})")
                            raise Exception("RATE_LIMIT_ERROR")

                        elif response.status_code == 503:
                            print(f"🎥 Agnes service unavailable (attempt {attempt+1}/{max_retries})")
                            raise Exception("SERVICE_UNAVAILABLE_ERROR")

                        else:
                            try:
                                error_data = response.json()
                                error_message = error_data.get("message", f"HTTP {response.status_code}")
                            except Exception:
                                error_message = f"HTTP {response.status_code}: {response.text}"

                            if "rate_limit" in error_message.lower() or "ServiceUnavailable" in error_message:
                                print(f"🎥 Agnes error requiring retry (attempt {attempt+1}/{max_retries}): {error_message}")
                                raise Exception("RETRY_REQUIRED_ERROR")

                            if response.status_code == 400:
                                raise Exception(f"视频参数错误: {error_message}")

                            raise Exception(f"创建视频任务失败: {error_message}")

                except Exception as e:
                    exc_msg = str(e)
                    if exc_msg in ("RATE_LIMIT_ERROR", "SERVICE_UNAVAILABLE_ERROR", "RETRY_REQUIRED_ERROR") and attempt < max_retries:
                        print(f"🎥 Will retry in {retry_wait} seconds...")
                        await asyncio.sleep(retry_wait)
                        continue
                    elif ("Connection" in exc_msg or "timeout" in exc_msg.lower()) and attempt < max_retries:
                        print(f"🎥 Connection issue: {exc_msg}, retrying in {retry_wait} seconds...")
                        await asyncio.sleep(retry_wait)
                        continue
                    else:
                        raise

                if task_id:
                    video_url = await self._poll_task_status(task_id, headers)
                    print(f"🎥 Agnes video generation completed, video URL: {video_url}")
                    return video_url

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
            print(f"🎥 Error generating video with Agnes: {error_msg}")
            traceback.print_exc()
            raise Exception(f"视频生成失败: {error_msg}")