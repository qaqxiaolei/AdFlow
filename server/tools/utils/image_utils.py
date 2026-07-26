import os
import traceback
from PIL import Image, PngImagePlugin
from io import BytesIO
import base64
import json
from typing import Any, Optional, Tuple
from nanoid import generate
from utils.http_client import HttpClient
from services.config_service import FILES_DIR


def generate_image_id() -> str:
    """生成唯一图像ID"""
    return generate(size=10)


async def get_image_info_and_save(
    url: str,
    file_path_without_extension: str,
    is_b64: bool = False,
    metadata: Optional[dict[str, Any]] = None
) -> Tuple[str, int, int, str]:
    """
    从URL下载图像或解码base64，转换为PNG并保存元数据

    参数:
        url: 图像URL或base64字符串
        file_path_without_extension: 不带扩展名的文件路径
        is_b64: url是否为base64字符串
        metadata: 要保存在PNG信息中的可选元数据

    返回:
        tuple[str, int, int, str]: (mime_type, width, height, extension) - 始终为PNG
    """
    try:
        if is_b64:
            image_data = base64.b64decode(url)
        else:
            image_data = await HttpClient.download_bytes(url)

        # Open image to get info
        image = Image.open(BytesIO(image_data))
        width, height = image.size
        
        # Store original format for debugging
        original_format = image.format or 'Unknown'
        print(f"Converting {original_format} image to PNG: {width}x{height}")

        # Handle different color modes properly for PNG conversion
        if image.mode == 'P':
            # Palette mode - convert to RGBA to preserve potential transparency
            if 'transparency' in image.info:
                image = image.convert('RGBA')
            else:
                image = image.convert('RGB')
        elif image.mode == 'LA':
            # Grayscale with alpha - convert to RGBA
            image = image.convert('RGBA')
        elif image.mode == 'L':
            # Grayscale - can stay as L or convert to RGB
            # PNG supports grayscale, so we can keep it
            pass
        elif image.mode == 'CMYK':
            # CMYK mode - convert to RGB
            image = image.convert('RGB')
        elif image.mode in ('RGB', 'RGBA'):
            # Already compatible with PNG
            pass
        else:
            # For any other modes, convert to RGB as a safe fallback
            print(f"Warning: Unusual color mode {image.mode}, converting to RGB")
            image = image.convert('RGB')

        # Unified format: always PNG
        extension = 'png'
        mime_type = 'image/png'

        # Prepare PNG info for metadata
        pnginfo = PngImagePlugin.PngInfo()
        
        # Add original format info
        pnginfo.add_text("original_format", original_format)
        
        if metadata:
            for key, value in metadata.items():
                try:
                    # Handle different value types
                    if isinstance(value, (dict, list)):
                        # Serialize complex types as JSON
                        text_value = json.dumps(value, ensure_ascii=False)
                    elif value is None:
                        text_value = "null"
                    else:
                        # Convert to string
                        text_value = str(value)
                    
                    pnginfo.add_text(str(key), text_value)
                except Exception as e:
                    print(f"Warning: Failed to add metadata key '{key}': {e}")
                    traceback.print_stack()

        # Save as PNG with metadata
        file_path = f"{file_path_without_extension}.{extension}"
        
        # Save with optimizations and metadata
        if metadata or original_format != 'PNG':
            image.save(file_path, format='PNG', optimize=True, pnginfo=pnginfo)
        else:
            image.save(file_path, format='PNG', optimize=True)
        
        print(f"Successfully saved as PNG: {file_path}")
        return mime_type, width, height, extension

    except Exception as e:
        print(f"Error processing image: {e}")
        raise e


# Canvas-related utilities have been moved to tools/image_generation/image_canvas_utils.py


# Canvas element generation moved to tools/image_generation/image_canvas_utils.py


# Canvas saving functionality moved to tools/image_generation/image_canvas_utils.py


# Image generation orchestration moved to tools/image_generation/image_generation_core.py
# Notification functions moved to tools/image_generation/image_canvas_utils.py


async def process_input_image(input_image: str | None) -> str | None:
    """
    Process input image and convert to base64 format

    Args:
        input_image: Image file path

    Returns:
        Base64 encoded image with data URL, or None if no image
    """
    if not input_image:
        return None

    try:
        full_path = os.path.join(FILES_DIR, input_image)
        if not os.path.exists(full_path):
            print(f"Warning: Image file not found: {full_path}")
            return None

        image = Image.open(full_path)
        ext = os.path.splitext(input_image)[1].lower()
        mime_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp'
        }
        mime_type = mime_type_map.get(ext, 'image/jpeg')

        with BytesIO() as output:
            image.save(output, format=str(mime_type.split('/')[1]).upper())
            compressed_data = output.getvalue()
            b64_data = base64.b64encode(compressed_data).decode('utf-8')

        data_url = f"data:{mime_type};base64,{b64_data}"
        return data_url

    except Exception as e:
        print(f"Error processing image {input_image}: {e}")
        return None


def get_image_base64(image_name: str) -> str:
    """Load local image and return a data-URL base64 string.

    Volces/Doubao video models only accept aspect ratios roughly in 0.4–2.5;
    out-of-range images are resized before encoding.
    """
    from mimetypes import guess_type

    image_path = os.path.join(FILES_DIR, f"{image_name}")
    image = Image.open(image_path)

    width, height = image.size
    ratio = width / height
    if ratio > 2.5 or ratio < 0.4:
        if ratio < 1:
            new_height = int(width * 2.4)
            new_width = width
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        elif ratio > 1:
            new_width = int(height * 2.4)
            new_height = height
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            new_width, new_height = image.size
    else:
        new_width, new_height = image.size

    scale_factor: float = float((float(1048576) / float(new_width * new_height)) ** 0.5)
    preview_image_width = int(new_width * scale_factor)
    preview_image_height = int(new_height * scale_factor)

    img = image.resize(
        (preview_image_width, preview_image_height), Image.Resampling.LANCZOS
    )
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format="PNG")

    b64 = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
    mime_type, _ = guess_type(image_path)
    if not mime_type:
        mime_type = "image/png"
    return f"data:{mime_type};base64,{b64}"
