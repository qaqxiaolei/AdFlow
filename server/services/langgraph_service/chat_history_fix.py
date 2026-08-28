"""修复不完整的 tool_call / ToolMessage 配对，避免 INVALID_CHAT_HISTORY。"""

from __future__ import annotations

from typing import Any, Dict, List, Set


def fix_openai_chat_history(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """为 OpenAI 格式历史补上缺失的 tool 结果消息。"""
    if not messages:
        return messages

    tool_call_ids: Set[str] = set()
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            tool_call_ids.add(str(msg.get("tool_call_id")))

    fixed_messages: List[Dict[str, Any]] = []
    for msg in messages:
        fixed_messages.append(msg)
        if msg.get("role") != "assistant" or not msg.get("tool_calls"):
            continue

        for tool_call in msg.get("tool_calls", []):
            tool_call_id = tool_call.get("id")
            if not tool_call_id or str(tool_call_id) in tool_call_ids:
                continue

            fn = tool_call.get("function") or {}
            name = fn.get("name") or tool_call.get("name") or "unknown_tool"
            print(
                f"[fix] missing ToolMessage recovered: {name} ({tool_call_id})"
            )
            fixed_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": name,
                    "content": (
                        f"<hide_in_user_ui> Tool {name} completed "
                        "(recovered missing tool result).</hide_in_user_ui>"
                    ),
                }
            )
            tool_call_ids.add(str(tool_call_id))

    return fixed_messages


def fix_langchain_messages(messages: List[Any]) -> List[Any]:
    """为 LangChain BaseMessage 列表补上缺失的 ToolMessage。"""
    from langchain_core.messages import AIMessage, ToolMessage

    if not messages:
        return messages

    tool_call_ids = {
        m.tool_call_id
        for m in messages
        if isinstance(m, ToolMessage) and m.tool_call_id
    }

    fixed: List[Any] = []
    for msg in messages:
        fixed.append(msg)
        if not isinstance(msg, AIMessage) or not msg.tool_calls:
            continue
        for tool_call in msg.tool_calls:
            tool_call_id = tool_call.get("id")
            if not tool_call_id or tool_call_id in tool_call_ids:
                continue
            name = tool_call.get("name") or "unknown_tool"
            print(
                f"[fix] pre_model_hook recovered ToolMessage: {name} ({tool_call_id})"
            )
            fixed.append(
                ToolMessage(
                    content=(
                        f"<hide_in_user_ui> Tool {name} completed "
                        "(recovered missing tool result).</hide_in_user_ui>"
                    ),
                    tool_call_id=tool_call_id,
                    name=name,
                )
            )
            tool_call_ids.add(tool_call_id)

    return fixed


def pre_model_hook_fix_history(state: Dict[str, Any]) -> Dict[str, Any]:
    """在每次调用 LLM 前补全不完整的 tool 对话，防止 handoff 后崩溃。"""
    messages = state.get("messages") or []
    fixed = fix_langchain_messages(list(messages))
    return {
        "messages": fixed,
        "llm_input_messages": fixed,
    }
