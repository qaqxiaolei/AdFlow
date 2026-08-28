"""视频工具参数兼容：LLM 常把 list 传成 JSON 字符串。"""

from __future__ import annotations

import json
from typing import Any


def coerce_input_images(value: Any) -> list[str] | None:
    """
    将 input_images 规范成 list[str]。
    接受：None、list、JSON 数组字符串、单个文件名字符串。
    """
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item).strip().strip("'\"") for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [
                        str(item).strip().strip("'\"")
                        for item in parsed
                        if str(item).strip()
                    ]
            except json.JSONDecodeError:
                pass
            # 兜底：简易拆分 ["a.png"] / ['a.png']
            inner = text.strip("[]").strip()
            if inner:
                parts = [
                    p.strip().strip("'\"")
                    for p in inner.split(",")
                    if p.strip().strip("'\"")
                ]
                if parts:
                    return parts
        return [text.strip("'\"")]
    return None
