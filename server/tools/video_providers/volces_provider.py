import traceback
import asyncio
import time
from typing import Optional, Dict, Any, List

import httpx

from .video_base_provider import VideoProviderBase
from utils.http_client import HttpClient
from services.config_service import config_service
from ..video_generation.video_canvas_utils import send_tool_call_progress

VOLCES_POLL_INTERVAL_SECONDS = 10
VOLCES_POLL_MAX_SECONDS = 600
VOLCES_NETWORK_MAX_RETRIES = 5


class VolcesVideoProvider(VideoProviderBase, provider_name="volces"):
    """火山方舟（Volces Ark）视频生成提供商"""

    def __init__(self):
        config = config_service.app_config.get('volces', {})
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("url", "").rstrip("/")
        self.model_name = config.get("model_name", "doubao-seedance-1-0-pro")

        if not self.api_key:
            raise ValueError("Volces API密钥未配置")
        if not self.base_url:
            raise ValueError("Volces URL未配置")

    def _is_seedance_v2(self, model: str) -> bool:
        normalized = model.lower().replace(".", "-")
        return "seedance-2" in normalized

    def _build_api_url(self) -> str:
        return f"{self.base_url}/contents/generations/tasks"

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",
        }

    def _append_images_to_content(
        self,
        content: List[Dict[str, Any]],
        input_image_data: Optional[List[str]],
    ) -> None:
        if not isinstance(input_image_data, list):
            return
        if len(input_image_data) == 1:
            content.append({
                "type": "image_url",
                "image_url": {"url": input_image_data[0]},
            })
        elif len(input_image_data) >= 2:
            content.append({
                "type": "image_url",
                "image_url": {"url": input_image_data[0]},
                "role": "first_frame",
            })
            content.append({
                "type": "image_url",
                "image_url": {"url": input_image_data[1]},
                "role": "last_frame",
            })

    def _build_seedance_v2_payload(
        self,
        prompt: str,
        model: str,
        resolution: str,
        duration: int,
        aspect_ratio: str,
        input_image_data: Optional[List[str]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        text = prompt.strip()
        negative_prompt = kwargs.get("negative_prompt")
        if negative_prompt:
            text = f"{text}\n\n请避免出现：{negative_prompt}"

        content: List[Dict[str, Any]] = [{"type": "text", "text": text}]
        self._append_images_to_content(content, input_image_data)

        clamped_duration = max(4, min(15, duration))
        ratio = aspect_ratio if input_image_data else aspect_ratio

        payload: Dict[str, Any] = {
            "model": model,
            "content": content,
            "duration": clamped_duration,
            "resolution": resolution,
            "ratio": ratio,
            "watermark": False,
            "generate_audio": kwargs.get("generate_audio", True),
        }
        return payload

    def _build_seedance_v1_payload(
        self,
        prompt: str,
        model: str | None,
        resolution: str,
        duration: int,
        aspect_ratio: str,
        camera_fixed: bool,
        input_image_data: Optional[List[str]],
    ) -> Dict[str, Any]:
        command = (
            f"--resolution {resolution} "
            f"--dur {duration} "
            f"--camerafixed {str(camera_fixed).lower()} "
            f"--wm false"
        )
        if not input_image_data:
            command += f" --rt {aspect_ratio}"

        content: List[Dict[str, Any]] = [
            {"type": "text", "text": prompt + " " + command}
        ]
        self._append_images_to_content(content, input_image_data)

        resolved_model = (
            str(self.model_name.split("by")[0]).rstrip("_")
            if model is None
            else model
        )
        return {"model": resolved_model, "content": content}

    def _build_request_payload(
        self,
        prompt: str,
        model: str | None = None,
        resolution: str = "480p",
        duration: int = 5,
        aspect_ratio: str = "16:9",
        camera_fixed: bool = True,
        input_image_data: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        resolved_model = model or self.model_name
        if self._is_seedance_v2(resolved_model):
            return self._build_seedance_v2_payload(
                prompt=prompt,
                model=resolved_model,
                resolution=resolution,
                duration=duration,
                aspect_ratio=aspect_ratio,
                input_image_data=input_image_data,
                **kwargs,
            )
        return self._build_seedance_v1_payload(
            prompt=prompt,
            model=model,
            resolution=resolution,
            duration=duration,
            aspect_ratio=aspect_ratio,
            camera_fixed=camera_fixed,
            input_image_data=input_image_data,
        )

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Dict[str, str],
        json: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        last_error: Optional[Exception] = None
        for attempt in range(VOLCES_NETWORK_MAX_RETRIES):
            try:
                if method.upper() == "GET":
                    return await client.get(url, headers=headers)
                return await client.post(url, headers=headers, json=json)
            except Exception as error:
                last_error = error
                if (
                    attempt >= VOLCES_NETWORK_MAX_RETRIES - 1
                    or not HttpClient._is_retryable_network_error(error)
                ):
                    raise
                wait_seconds = min(3 * (2 ** attempt), 15)
                print(
                    f"⚠️ [Volces] 网络异常 (尝试 {attempt + 1}/{VOLCES_NETWORK_MAX_RETRIES}): "
                    f"{error}，{wait_seconds}s 后重试..."
                )
                await asyncio.sleep(wait_seconds)
        if last_error:
            raise last_error
        raise RuntimeError(f"Volces request failed: {url}")

    async def _poll_task_status(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        headers: Dict[str, str],
        session_id: str = "",
        tool_call_id: str = "",
    ) -> str:
        polling_url = f"{self.base_url}/contents/generations/tasks/{task_id}"
        status = "submitted"
        started_at = time.monotonic()

        while status not in ("succeeded", "completed", "failed", "cancelled"):
            elapsed = time.monotonic() - started_at
            if elapsed > VOLCES_POLL_MAX_SECONDS:
                raise Exception(
                    f"火山方舟视频任务轮询超时（>{VOLCES_POLL_MAX_SECONDS}s），"
                    f"task_id={task_id}，最后状态={status}"
                )

            print(
                f"🎥 Polling Volces generation {task_id}, "
                f"status={status}, elapsed={elapsed:.0f}s"
            )
            if session_id and tool_call_id:
                await send_tool_call_progress(
                    session_id,
                    tool_call_id,
                    f"视频生成中（已等待 {int(elapsed)} 秒）...",
                )

            await asyncio.sleep(VOLCES_POLL_INTERVAL_SECONDS)

            poll_response = await self._request_with_retry(
                client, "GET", polling_url, headers
            )
            if poll_response.status_code != 200:
                raise Exception(
                    f"Volces poll failed: HTTP {poll_response.status_code} "
                    f"{poll_response.text[:200]}"
                )

            poll_res = poll_response.json()
            status = poll_res.get("status")

            if status in ("succeeded", "completed"):
                content = poll_res.get("content", {})
                output = content.get("video_url") if isinstance(content, dict) else None
                if output and isinstance(output, str):
                    return output
                raise Exception("No video URL found in successful response")
            if status in ("failed", "cancelled"):
                detail_error = poll_res.get(
                    "error",
                    poll_res.get("detail", f"Task failed with status: {status}"),
                )
                raise Exception(f"Volces video generation failed: {detail_error}")

        raise Exception(f"Task polling failed with final status: {status}")

    async def generate(
        self,
        prompt: str,
        model: str,
        resolution: str = "480p",
        duration: int = 5,
        aspect_ratio: str = "16:9",
        input_images: Optional[List[str]] = None,
        camera_fixed: bool = True,
        **kwargs: Any,
    ) -> str:
        try:
            api_url = self._build_api_url()
            headers = self._build_headers()
            input_image_data = input_images if input_images else None

            payload = self._build_request_payload(
                prompt=prompt,
                model=model,
                resolution=resolution,
                duration=duration,
                aspect_ratio=aspect_ratio,
                camera_fixed=camera_fixed,
                input_image_data=input_image_data,
                **kwargs,
            )

            print(
                f"🎥 Starting Volces video generation, model={payload.get('model')}"
            )

            session_id = str(kwargs.get("session_id", ""))
            tool_call_id = str(kwargs.get("tool_call_id", ""))
            timeout = httpx.Timeout(600.0, connect=120.0)

            async with HttpClient.create(timeout=timeout) as client:
                create_response = await self._request_with_retry(
                    client, "POST", api_url, headers, json=payload
                )
                if create_response.status_code != 200:
                    try:
                        error_data = create_response.json()
                        error_message = error_data.get("error", error_data)
                    except Exception:
                        error_message = (
                            f"HTTP {create_response.status_code} "
                            f"{create_response.text[:200]}"
                        )
                    raise Exception(f"Volces task creation failed: {error_message}")

                result = create_response.json()
                task_id = result.get("id")
                if not task_id:
                    print("🎥 Failed to create Volces video generation task:", result)
                    raise Exception("Volces video generation task creation failed")

                print(f"🎥 Volces video generation task created, task_id: {task_id}")

                video_url = await self._poll_task_status(
                    client,
                    task_id,
                    headers,
                    session_id=session_id,
                    tool_call_id=tool_call_id,
                )

            print(f"🎥 Volces video generation completed, video URL: {video_url}")
            return video_url

        except Exception as e:
            print(f"🎥 Error generating video with Volces: {str(e)}")
            traceback.print_exc()
            raise e
