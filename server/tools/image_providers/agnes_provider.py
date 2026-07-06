import os
import traceback
import asyncio
from typing import Optional, Any
from openai import OpenAI
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
        self.base_url = str(config.get("url", ""))

        if not self.api_key:
            raise ValueError("Agnes API key is not configured")

        http_client = httpx.Client(
            timeout=httpx.Timeout(60.0, connect=30.0),
            retries=httpx.Retry(
                total=3,
                backoff_factor=1.0,
                status_codes=[429, 500, 502, 503, 504]
            )
        )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url or None,
            http_client=http_client
        )

        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                if input_images and len(input_images) > 0:
                    input_image_path = input_images[0]
                    full_path = os.path.join(FILES_DIR, input_image_path)

                    with open(full_path, 'rb') as image_file:
                        result = self.client.images.edit(
                            model=model,
                            image=image_file,
                            prompt=prompt,
                            n=kwargs.get("num_images", 1)
                        )
                else:
                    size_map = {
                        "1:1": "1024x1024",
                        "16:9": "1792x1024",
                        "9:16": "1024x1792",
                        "4:3": "1024x768",
                        "3:4": "768x1024"
                    }
                    size = size_map.get(aspect_ratio, "1024x1024")

                    result = self.client.images.generate(
                        model=model,
                        prompt=prompt,
                        n=kwargs.get("num_images", 1),
                        size=size,
                    )

                if not result.data or len(result.data) == 0:
                    raise Exception("No image data returned from Agnes API")

                image_data = result.data[0]

                if hasattr(image_data, 'b64_json') and image_data.b64_json:
                    image_b64 = image_data.b64_json
                    image_id = generate_image_id()
                    mime_type, width, height, extension = await get_image_info_and_save(
                        image_b64, os.path.join(FILES_DIR, f'{image_id}'), is_b64=True
                    )
                elif hasattr(image_data, 'url') and image_data.url:
                    image_url = image_data.url
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