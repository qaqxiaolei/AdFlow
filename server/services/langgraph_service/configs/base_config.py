from typing import Annotated, Optional, Dict, Any, Sequence, List
from typing_extensions import TypedDict
from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool  # type: ignore
from langgraph_swarm.handoff import METADATA_KEY_HANDOFF_DESTINATION
from models.tool_model import ToolInfoJson


class ToolConfig(TypedDict):
    """工具配置"""
    tool: str


def _normalize_agent_name(name: str) -> str:
    """标准化智能体名称以兼容工具名称。"""
    return name.lower().replace(" ", "_").replace("-", "_")


def create_handoff_tool(
    *, agent_name: str, name: Optional[str] = None, description: Optional[str] = None
) -> BaseTool:
    """创建一个可以将控制权切换到指定智能体的工具。

    参数:
        agent_name: 要切换控制权的智能体名称，即多智能体图中的智能体节点名称。
            智能体名称应简洁、清晰且唯一，最好使用snake_case格式，
            虽然您只受限于LangGraph节点接受的名称以及LLM提供商接受的工具名称
            (工具名称将如下所示: `transfer_to_<agent_name>`)。
        name: 用于切换的工具的可选名称。
            如果未提供，工具名称将为 `transfer_to_<agent_name>`。
        description: 切换工具的可选描述。
            如果未提供，工具描述将为 `Ask agent <agent_name> for help`。
    """
    if name is None:
        name = f"transfer_to_{_normalize_agent_name(agent_name)}"

    if description is None:
        description = f"Ask agent '{agent_name}' for help"

    @tool(name, description=description+"""
    \nIMPORTANT RULES:
            1. You MUST complete the other tool calls and wait for their result BEFORE attempting to transfer to another agent
            2. Do NOT call this handoff tool with other tools simultaneously
            3. Always wait for the result of other tool calls before making this handoff call
    """)
    def handoff_to_agent(
        state: Annotated[Dict[str, Any], InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command[Any]:
        tool_message = ToolMessage(
            content=f"<hide_in_user_ui> Successfully transferred to {agent_name}",
            name=name,
            tool_call_id=tool_call_id,
        )
        return Command(
            goto=agent_name,
            graph=Command.PARENT,
            update={"messages": state["messages"] +
                    [tool_message], "active_agent": agent_name},
        )

    setattr(handoff_to_agent, 'metadata', {
            METADATA_KEY_HANDOFF_DESTINATION: agent_name})

    return handoff_to_agent


class HandoffConfig(TypedDict):
    """切换智能体配置"""
    agent_name: str
    description: str


class BaseAgentConfig:
    """智能体配置基类

    此类用于存储智能体配置信息的配置类，不是实际的智能体。
    实际的智能体将通过 LangGraph 的 create_react_agent 函数创建。
    """

    def __init__(
        self,
        name: str,
        tools: Sequence[ToolInfoJson],
        system_prompt: str,
        handoffs: Optional[List[HandoffConfig]] = None
    ) -> None:
        self.name = name
        self.tools = tools
        self.system_prompt = system_prompt
        self.handoffs: List[HandoffConfig] = handoffs or []