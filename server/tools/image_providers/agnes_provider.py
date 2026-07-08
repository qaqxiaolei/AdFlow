import os
import json
import traceback
import asyncio
from typing import Optional, Any, Dict
import httpx
from .image_base_provider import ImageProviderBase
from ..utils.image_utils import get_image_info_and_save, generate_image_id
from ..agnes_api_routes import (
    AGNES_IMAGE_API_ROUTE,
    build_image_api_url,
)
from ..agnes_model_config import (
    AGNES_IMAGE_MODELS,
    AGNES_IMAGE_MODEL_DEFAULT,
    is_valid_image_model,
)
from services.config_service import FILES_DIR
from services.config_service import config_service


class AgnesImageProvider(ImageProviderBase):
    """Agnes AI image generation provider implementation"""
    def __init__(self):
        """
        初始化 Agnes 图片生成提供者
        启动时预请求基础接口，提前拦截无效地址配置
        """
        config = config_service.app_config.get('agnes', {})
        self.api_key = str(config.get("api_key", ""))
        self.base_url = str(config.get("url", "")).rstrip("/")
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
            api_url = build_image_api_url(self.base_url)
            headers = self._build_headers()
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                    response = await client.options(api_url, headers=headers)
                    if response.status_code == 404:
                        print(f"⚠️ [Agnes-Image] API 端点不可用: {api_url}")
                        print(f"⚠️ [Agnes-Image] 请核对 Agnes 服务接口路由配置")
                    else:
                        print(f"✅ [Agnes-Image] API 端点校验通过: {api_url}")
                        print(f"✅ [Agnes-Image] 可用模型列表: {AGNES_IMAGE_MODELS}")
            except Exception as e:
                print(f"⚠️ [Agnes-Image] API 端点检测失败: {e}")
                print(f"⚠️ [Agnes-Image] URL: {api_url}")
        try:
            asyncio.get_event_loop().create_task(check_endpoint())
        except Exception:
            pass

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _is_model_not_found_error(self, response: httpx.Response) -> bool:
        """
        判断是否为模型不可用错误

        Args:
            response: HTTP 响应对象

        Returns:
            是否为 model_not_found 错误
        """
        if response.status_code != 503:
            return False
        try:
            error_data = response.json()
            return error_data.get("error", {}).get("code") == "model_not_found"
        except Exception:
            return False

    def _extract_error_info(self, response: httpx.Response) -> dict:
        """
        从响应中提取错误信息
        Args:
            response: HTTP 响应对象
        Returns:
            错误信息字典
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
            # 尝试提取请求ID（不同API格式可能不同）
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

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_images: Optional[list[str]] = None,
        **kwargs: Any
    ) -> tuple[str, int, int, str]:
        # 【预校验机制】发起请求前检查模型是否在白名单中
        if not is_valid_image_model(model):
            raise ValueError(
                f"图像模型 '{model}' 不在可用白名单中。"
                f"可用图像模型: {AGNES_IMAGE_MODELS}"
            )
        headers = self._build_headers()
        api_url = build_image_api_url(self.base_url)
        # 准备模型列表：优先使用指定模型，其次使用配置的备用模型
        models_to_try = [model]
        if model == AGNES_IMAGE_MODEL_DEFAULT:
            models_to_try.extend([m for m in AGNES_IMAGE_MODELS if m != model])
        print(f"🖼️ [Agnes-Image] 准备尝试的模型列表: {models_to_try}")
        last_error = None
        request_id = ""
        for attempt_idx, current_model in enumerate(models_to_try):
            try:
                size_map = {
                    "1:1": "1024x1024",
                    "16:9": "1792x1024",
                    "9:16": "1024x1792",
                    "4:3": "1024x768",
                    "3:4": "768x1024"
                }
                size = size_map.get(aspect_ratio, "1024x1024")
                payload = {
                    "model": current_model,
                    "prompt": prompt,
                    "n": kwargs.get("num_images", 1),
                    "size": size,
                }
                if input_images and len(input_images) > 0:
                    payload["input_images"] = input_images
                # 请求前打印完整请求URL日志，方便排查地址错误
                print(f"🖼️ [Agnes-Image] 请求URL: {api_url}")
                print(f"🖼️ [Agnes-Image] 请求模型: {current_model} (尝试 {attempt_idx + 1}/{len(models_to_try)})")
                print(f"🖼️ [Agnes-Image] 请求参数: {json.dumps(payload, ensure_ascii=False)[:200]}...")
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=30.0)) as client:
                    response = await client.post(api_url, json=payload, headers=headers)
                    # 404错误捕获
                    if response.status_code == 404:
                        print(f"🖼️ [Agnes-Image] API 返回404: {response.text[:100]}")
                        raise Exception("图片生成接口地址无效，请核对Agnes服务接口路由配置")
                    # 503错误处理（包含model_not_found）
                    if response.status_code == 503:
                        error_info = self._extract_error_info(response)
                        request_id = error_info["request_id"]
                        print(f"🖼️ [Agnes-Image] API 返回503 - 请求ID: {request_id}, 错误码: {error_info['error_code']}, 错误信息: {error_info['error_message']}")
                        if error_info["error_code"] == "model_not_found":
                            # 【模型降级逻辑】model_not_found时尝试备用模型
                            if attempt_idx < len(models_to_try) - 1:
                                next_model = models_to_try[attempt_idx + 1]
                                print(f"🖼️ [Agnes-Image] 模型 '{current_model}' 通道不可用，自动降级到备用模型 '{next_model}'")
                                last_error = error_info
                                continue
                            # 所有模型都不可用，抛出清晰错误
                            raise Exception(
                                f"图像模型通道不可用。所有配置的图像模型均无法访问。"
                                f"尝试过的模型: {models_to_try}。"
                                f"请求ID: {request_id}。"
                                f"请联系服务商开通图像生成权限或切换可用图像模型。"
                            )
                        raise Exception(f"Agnes API 服务不可用: {error_info['error_message']}")
                    if response.status_code != 200:
                        error_info = self._extract_error_info(response)
                        request_id = error_info["request_id"]
                        print(f"🖼️ [Agnes-Image] API 请求失败 - 请求ID: {request_id}, 状态码: {response.status_code}, 错误: {error_info['error_message']}")
                        raise Exception(f"Agnes API 请求失败: HTTP {response.status_code} - {error_info['error_message']}")
                    result = response.json()
                if not result.get("data") or len(result["data"]) == 0:
                    raise Exception("No image data returned from Agnes API")
                image_data = result["data"][0]
                if image_data.get('b64_json'):
                    image_b64 = image_data['b64_json']
                    image_id = generate_image_id()
                    mime_type, width, height, extension = await get_image_info_and_save(
                        image_b64, os.path.join(FILES_DIR, f'{image_id}'), is_b64=True
                    )
                elif image_data.get('url'):
                    image_url = image_data['url']
                    image_id = generate_image_id()
                    mime_type, width, height, extension = await get_image_info_and_save(
                        image_url, os.path.join(FILES_DIR, f'{image_id}')
                    )
                else:
                    raise Exception("Invalid response format from Agnes API")
                if mime_type is None:
                    raise Exception('Failed to determine image MIME type')
                filename = f'{image_id}.{extension}'
                print(f"🖼️ [Agnes-Image] 图片生成成功 - 模型: {current_model}, 文件名: {filename}, 尺寸: {width}x{height}")
                return mime_type, width, height, filename
            except Exception as e:
                error_msg = str(e)
                print(f'🖼️ [Agnes-Image] 图片生成失败 (模型: {current_model}, 尝试 {attempt_idx + 1}/{len(models_to_try)}): {error_msg}')
                traceback.print_exc()
                # 如果是404错误，直接抛出，不再重试
                if "图片生成接口地址无效" in error_msg or "404" in error_msg:
                    raise e
                # 如果是所有模型都尝试过了，抛出最终错误
                if attempt_idx >= len(models_to_try) - 1:
                    raise e
                # 否则继续尝试下一个模型
                last_error = e
                continue
        # 理论上不会到达这里，因为上面会抛出异常
        if last_error:
            raise last_error
        raise Exception("图片生成失败")

#  声明本图片生成模块，对外仅暴露 AgnesImageProvider 这一个图片生成提供器类，其他内部代码禁止外部通过 import * 引用
__all__ = ["AgnesImageProvider"]
