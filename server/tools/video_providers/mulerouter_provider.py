"""MuleRouter Berry 1.0 视频生成。创建任务后轮询，不删除任务。"""

from __future__ import annotations

import asyncio
import base64
import os
import time
import traceback
from io import BytesIO
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image

from services.config_service import config_service
from utils.http_client import HttpClient
from .video_base_provider import VideoProviderBase

BERRY_POLL_INTERVAL_SECONDS = 8
BERRY_POLL_MAX_SECONDS = 900
BERRY_NETWORK_MAX_RETRIES = 3
BERRY_RATIOS = {"16:9", "4:3", "1:1", "3:4", "9:16", "adaptive"}
BERRY_RESOLUTIONS = {"480p", "720p", "1080p"}
BERRY_PATH = "/vendors/carrothub/v1/berry-1.0/generation"


class MuleRouterVideoProvider(VideoProviderBase, provider_name="mulerouter"):
    """Berry 1.0（MuleRouter）。文生视频、首尾帧、多参考图。"""

    def __init__(self):
        config = config_service.app_config.get("mulerouter", {})
        self.api_key = (
            os.environ.get("MULEROUTER_API_KEY", "").strip()
            or str(config.get("api_key", "")).strip()
        )
        self.base_url = (
            str(config.get("url") or "https://api.mulerouter.ai").rstrip("/")
        )
        if not self.api_key:
            raise ValueError(
                "未配置 MuleRouter API Key。请在 server/.env 设置 MULEROUTER_API_KEY 后重启服务"
            )

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _task_url(self, task_id: str = "") -> str:
        url = f"{self.base_url}{BERRY_PATH}"
        if task_id:
            return f"{url}/{task_id}"
        return url

    def _flatten_image(self, value: str) -> str:
        """Berry 不接受带透明通道的 PNG。公网 URL 原样传递。"""
        if not value.startswith("data:"):
            return value
        try:
            _, b64 = value.split(",", 1)
            image = Image.open(BytesIO(base64.b64decode(b64)))
            has_alpha = image.mode in ("RGBA", "LA") or (
                image.mode == "P" and "transparency" in image.info
            )
            if not has_alpha:
                return value
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[-1])
            buf = BytesIO()
            background.save(buf, format="JPEG", quality=90)
            encoded = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{encoded}"
        except Exception:
            return value

    def _normalize_ratio(self, aspect_ratio: str) -> str:
        ratio = (aspect_ratio or "9:16").strip().replace("/", ":")
        if ratio in BERRY_RATIOS:
            return ratio
        if ratio == "21:9":
            return "16:9"
        if ratio == "3:2":
            return "4:3"
        return "9:16"

    def _normalize_resolution(self, resolution: str) -> str:
        value = (resolution or "480p").strip().lower()
        if value in BERRY_RESOLUTIONS:
            return value
        return "480p"

    def _normalize_duration(self, duration: int) -> int:
        try:
            seconds = int(duration)
        except (TypeError, ValueError):
            return 5
        if seconds == -1:
            return -1
        return max(2, min(30, seconds))

    def _build_payload(
        self,
        prompt: str,
        resolution: str,
        duration: int,
        aspect_ratio: str,
        input_images: Optional[List[str]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "resolution": self._normalize_resolution(resolution),
            "ratio": self._normalize_ratio(aspect_ratio),
            "duration": self._normalize_duration(duration),
            "audio": True,
        }
        images = [self._flatten_image(item) for item in (input_images or []) if item]
        if len(images) == 1:
            payload["first_frame"] = images[0]
        elif len(images) == 2:
            payload["first_frame"] = images[0]
            payload["last_frame"] = images[1]
        elif len(images) > 2:
            payload["reference_images"] = images[:10]
        return payload

    def _error_text(self, data: Any) -> str:
        if not isinstance(data, dict):
            return str(data)
        info = data.get("task_info") if isinstance(data.get("task_info"), dict) else {}
        err = info.get("error") or data.get("error") or data.get("detail") or data
        if isinstance(err, dict):
            return str(err.get("detail") or err.get("title") or err)
        return str(err)

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        last_error: Optional[Exception] = None
        for attempt in range(BERRY_NETWORK_MAX_RETRIES):
            try:
                if method.upper() == "GET":
                    return await client.get(url, headers=self._headers())
                return await client.post(url, headers=self._headers(), json=json_body)
            except Exception as error:
                last_error = error
                if (
                    attempt >= BERRY_NETWORK_MAX_RETRIES - 1
                    or not HttpClient._is_retryable_network_error(error)
                ):
                    raise
                await asyncio.sleep(min(3 * (2 ** attempt), 15))
        if last_error:
            raise last_error
        raise RuntimeError(f"MuleRouter request failed: {url}")

    async def _poll(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        session_id: str,
        tool_call_id: str,
    ) -> str:
        status = "pending"
        started_at = time.monotonic()
        while status not in ("completed", "failed"):
            elapsed = time.monotonic() - started_at
            if elapsed > BERRY_POLL_MAX_SECONDS:
                raise Exception(
                    f"Berry 视频任务轮询超时（>{BERRY_POLL_MAX_SECONDS}s），task_id={task_id}"
                )
            print(
                f"🎥 Polling Berry generation {task_id}, "
                f"status={status}, elapsed={elapsed:.0f}s"
            )
            if session_id and tool_call_id:
                from ..video_generation.video_canvas_utils import (
                    send_tool_call_progress,
                )

                await send_tool_call_progress(
                    session_id,
                    tool_call_id,
                    f"Berry 视频生成中（已等待 {int(elapsed)} 秒）...",
                )
            await asyncio.sleep(BERRY_POLL_INTERVAL_SECONDS)
            response = await self._request_with_retry(
                client, "GET", self._task_url(task_id)
            )
            if response.status_code != 200:
                raise Exception(
                    f"Berry 查询失败: HTTP {response.status_code} {response.text[:200]}"
                )
            data = response.json()
            info = data.get("task_info") if isinstance(data, dict) else {}
            status = str((info or {}).get("status") or "")
            if status == "completed":
                videos = data.get("videos") if isinstance(data, dict) else None
                if isinstance(videos, list) and videos and isinstance(videos[0], str):
                    return videos[0]
                raise Exception("Berry 任务已完成，但没有返回视频地址")
            if status == "failed":
                raise Exception(f"Berry 视频生成失败: {self._error_text(data)}")
        raise Exception(f"Berry 任务结束状态异常: {status}")

    async def generate(
        self,
        prompt: str,
        model: str,
        resolution: str = "480p",
        duration: int = 5,
        aspect_ratio: str = "9:16",
        input_images: Optional[List[str]] = None,
        camera_fixed: bool = True,
        **kwargs: Any,
    ) -> str:
        del model, camera_fixed
        try:
            payload = self._build_payload(
                prompt=prompt,
                resolution=resolution,
                duration=duration,
                aspect_ratio=aspect_ratio,
                input_images=input_images,
            )
            print(
                f"🎥 Starting Berry video generation, "
                f"resolution={payload['resolution']}, ratio={payload['ratio']}, "
                f"duration={payload['duration']}, images={len(input_images or [])}"
            )
            session_id = str(kwargs.get("session_id", ""))
            tool_call_id = str(kwargs.get("tool_call_id", ""))
            timeout = httpx.Timeout(900.0, connect=120.0)
            async with HttpClient.create_long_poll(timeout=timeout) as client:
                create_response = await self._request_with_retry(
                    client, "POST", self._task_url(), payload
                )
                if create_response.status_code != 200:
                    try:
                        error_message = self._error_text(create_response.json())
                    except Exception:
                        error_message = (
                            f"HTTP {create_response.status_code} "
                            f"{create_response.text[:200]}"
                        )
                    raise Exception(f"Berry 创建任务失败: {error_message}")

                created = create_response.json()
                info = created.get("task_info") if isinstance(created, dict) else {}
                task_id = str((info or {}).get("id") or "")
                if not task_id:
                    raise Exception(f"Berry 创建任务未返回 task id: {created}")
                print(f"🎥 Berry video generation task created, task_id: {task_id}")
                video_url = await self._poll(
                    client, task_id, session_id, tool_call_id
                )
            print(f"🎥 Berry video generation completed, video URL: {video_url}")
            return video_url
        except Exception as error:
            print(f"🎥 Error generating video with Berry: {error}")
            traceback.print_exc()
            raise
