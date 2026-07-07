import os
import traceback
import asyncio
from typing import Optional, Any, Dict
import httpx
from .image_base_provider import ImageProviderBase
from ..utils.image_utils import get_image_info_and_save, generate_image_id
from services.config_service import FILES_DIR
from services.config_service import config_service


class AgnesImageProvider(ImageProviderBase):
    """Agnes AI image generation provider implementation"""

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_images: Optional[list[str]] = None,
        **kwargs: Any
    ) -> tuple[str, int, int, str]:
        config = config_service.app_config.get('agnes', {})
        self.api_key = str(config.get("api_key", ""))
        self.base_url = str(config.get("url", "")).rstrip("/")

        if not self.api_key:
            raise ValueError("Agnes API key is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
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
                    "model": model,
                    "prompt": prompt,
                    "n": kwargs.get("num_images", 1),
                    "size": size,
                }

                if input_images and len(input_images) > 0:
                    payload["input_images"] = input_images

                api_url = f"{self.base_url}/images"

                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=30.0)) as client:
                    response = await client.post(api_url, json=payload, headers=headers)

                    if response.status_code != 200:
                        error_text = response.text
                        try:
                            error_data = response.json()
                            error_message = error_data.get("message", error_data.get("detail", error_text))
                        except Exception:
                            error_message = error_text
                        raise Exception(f"Agnes API request failed: HTTP {response.status_code} - {error_message}")

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
                return mime_type, width, height, filename

            except Exception as e:
                print(f'Error generating image with Agnes (attempt {attempt + 1}/{max_retries}):', e)
                traceback.print_exc()

                if attempt < max_retries - 1:
                    print(f'Retrying in {retry_delay} seconds...')
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise e