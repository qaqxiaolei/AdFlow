"""检测模型把工具调用写成普通文本（假 tool_call）的情况。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# 常见「文本假调用」形态：XML tool_call、function=、invoke 工具名等
_FAKE_TOOL_CALL_RE = re.compile(
    r"""
    <\s*tool_call\b
    | <\s*/\s*tool_call\s*>
    | <\s*function\s*=
    | <\s*tool\s*=
    | \binvoke\s+generate_(?:video|image)_by_agnes\b
    | \bcall\s+generate_(?:video|image)_by_agnes\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_FAKE_TOOL_CALL_STRIP_RE = re.compile(
    r"""
    <\s*tool_call\b[^>]*>.*?<\s*/\s*tool_call\s*>
    | <\s*function\s*=[^>]*>.*?<\s*/\s*function\s*>
    | <\s*tool\s*=[^>]*>.*?<\s*/\s*tool\s*>
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)

RETRY_CORRECTION_MESSAGE = (
    "<hide_in_user_ui>"
    "系统提示：你刚才用纯文本写出了 tool_call / function 标签，"
    "这不会真正执行任何工具，用户也看不到生成结果。"
    "请立刻通过 function call 接口调用对应工具"
    "（视频用 generate_video_by_agnes，图像用 generate_image_by_agnes），"
    "并填写完整参数（至少包含 prompt）。"
    "禁止再输出任何 <tool_call>、<function=...> 或类似 XML/Markdown 伪调用。"
    "</hide_in_user_ui>"
)


def _extract_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return str(content)


def looks_like_fake_tool_call_text(text: str) -> bool:
    if not text or not text.strip():
        return False
    return bool(_FAKE_TOOL_CALL_RE.search(text))


def strip_fake_tool_call_text(text: str) -> str:
    if not text:
        return text
    cleaned = _FAKE_TOOL_CALL_STRIP_RE.sub("", text)
    # 残留的单行伪标签
    cleaned = re.sub(
        r"<\s*/?\s*(?:tool_call|function|tool)\b[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def get_last_assistant_message(
    messages: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return msg
    return None


def is_textual_fake_tool_call(message: Optional[Dict[str, Any]]) -> bool:
    """assistant 消息无真实 tool_calls，但 content 里含伪工具调用文本。"""
    if not message or message.get("role") != "assistant":
        return False
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        return False
    return looks_like_fake_tool_call_text(_extract_text(message.get("content")))


def sanitize_assistant_message_content(
    message: Dict[str, Any],
) -> Dict[str, Any]:
    """去掉假 tool_call 文本，避免污染历史与前端展示。"""
    content = message.get("content")
    if isinstance(content, str):
        return {**message, "content": strip_fake_tool_call_text(content)}
    if isinstance(content, list):
        new_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = strip_fake_tool_call_text(str(part.get("text") or ""))
                if text:
                    new_parts.append({**part, "text": text})
            else:
                new_parts.append(part)
        return {**message, "content": new_parts}
    return message
