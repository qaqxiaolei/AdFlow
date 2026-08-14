import traceback
from typing import Dict
from langchain_core.tools import BaseTool
from models.tool_model import ToolInfo
from tools.write_plan import write_plan_tool
from tools.generate_image_by_agnes import generate_image_by_agnes
from tools.generate_video_by_agnes import generate_video_by_agnes
from tools.generate_video_by_seedance_v1_pro_volces import (
    generate_video_by_seedance_v1_pro_volces,
)
from tools.generate_video_by_seedance_v1_lite_volces import (
    generate_video_by_seedance_v1_lite_t2v,
    generate_video_by_seedance_v1_lite_i2v,
)
from tools.search_video_by_platform import search_video_by_platform_tool
from services.config_service import config_service

TOOL_MAPPING: Dict[str, ToolInfo] = {
    # 图像：仅保留 Agnes
    "generate_image_by_agnes": {
        "display_name": "Agnes Image",
        "type": "image",
        "provider": "agnes",
        "tool_function": generate_image_by_agnes,
    },
    # 视频工具保持不变
    "generate_video_by_agnes": {
        "display_name": "Seedance 2.0",
        "type": "video",
        "provider": "volces",
        "tool_function": generate_video_by_agnes,
    },
    "generate_video_by_seedance_v1_pro_volces": {
        "display_name": "Doubao Seedance v1 by volces",
        "type": "video",
        "provider": "volces",
        "tool_function": generate_video_by_seedance_v1_pro_volces,
    },
    "generate_video_by_seedance_v1_lite_volces_t2v": {
        "display_name": "Doubao Seedance v1 lite(text-to-video)",
        "type": "video",
        "provider": "volces",
        "tool_function": generate_video_by_seedance_v1_lite_t2v,
    },
    "generate_video_by_seedance_v1_lite_i2v_volces": {
        "display_name": "Doubao Seedance v1 lite(images-to-video)",
        "type": "video",
        "provider": "volces",
        "tool_function": generate_video_by_seedance_v1_lite_i2v,
    },
    "search_video_by_platform": {
        "display_name": "Video Search",
        "type": "search",
        "provider": "system",
        "tool_function": search_video_by_platform_tool,
    },
}


class ToolService:
    def __init__(self):
        self.tools: Dict[str, ToolInfo] = {}
        self._register_required_tools()

    def _register_required_tools(self):
        try:
            self.tools["write_plan"] = {
                "provider": "system",
                "tool_function": write_plan_tool,
            }
        except ImportError as e:
            print(f"❌ 注册必须工具失败 write_plan: {e}")

        try:
            self.tools["search_video_by_platform"] = {
                "provider": "system",
                "tool_function": search_video_by_platform_tool,
                "display_name": "Video Search",
                "type": "search",
            }
        except ImportError as e:
            print(f"❌ 注册必须工具失败 search_video_by_platform: {e}")

    def register_tool(self, tool_id: str, tool_info: ToolInfo):
        if tool_id in self.tools:
            print(f"🔄 TOOL ALREADY REGISTERED: {tool_id}")
            return

        self.tools[tool_id] = tool_info

    async def initialize(self):
        self.clear_tools()
        try:
            for provider_name, provider_config in config_service.app_config.items():
                if provider_config.get("api_key", ""):
                    for tool_id, tool_info in TOOL_MAPPING.items():
                        if tool_info.get("provider") == provider_name:
                            self.register_tool(tool_id, tool_info)
            # 生图仅使用 Agnes，不再注册 ComfyUI / Replicate 等其它图像工具
        except Exception as e:
            print(f"❌ Failed to initialize tool service: {e}")
            traceback.print_stack()

    def get_tool(self, tool_name: str) -> BaseTool | None:
        tool_info = self.tools.get(tool_name)
        return tool_info.get("tool_function") if tool_info else None

    def remove_tool(self, tool_id: str):
        self.tools.pop(tool_id)

    def get_all_tools(self) -> Dict[str, ToolInfo]:
        return self.tools.copy()

    def clear_tools(self):
        self.tools.clear()
        self._register_required_tools()


tool_service = ToolService()
