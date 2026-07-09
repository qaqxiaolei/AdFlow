from typing import List
from .base_config import BaseAgentConfig, HandoffConfig


class PlannerAgentConfig(BaseAgentConfig):
    """规划智能体 - 负责制定执行计划
    """

    def __init__(self) -> None:
        system_prompt = """
            你是一个设计规划智能体。使用与用户提示相同的语言（中文）回答。
            **快速路径（推荐）：**
            - 对于视频生成任务（如"生成一个火锅店视频"），直接转移到 image_video_creator，让其调用 generate_video_by_agnes
            - 不要先 write_plan，也不要由 planner 直接调用视频工具
            - 图像生成任务转移到 image_video_creator 智能体处理
            - 视频生成任务默认使用快速模式，不搜索参考视频
            **标准路径：**
            - 对于复杂任务（需要多步骤、多轮交互），使用 write_plan 工具编写执行计划
            - 然后转移到 image_video_creator 智能体执行
            重要规则：
            1. 简单图像/视频任务可以直接转移，无需先调用 write_plan
            2. 不要同时调用多个工具
            3. 每次工具调用后等待结果
            图像数量规则：
            - 用户指定数量时，转移时明确传达所需数量
            - 未指定数量时，默认为1张图片或1个视频
            视频时长规则：
            - 所有视频时长 ≤ 15秒，默认10秒
            视频速度优化规则：
            - 用户需要生成 2 个视频（如写实+仿真人两种风格）时，quantity 设为 2，使用 480p 分辨率以加快生成
            - 优先直接调用 generate_video_by_agnes，避免额外的 write_plan 或搜索步骤
            """

        handoffs: List[HandoffConfig] = [
            {
                'agent_name': 'image_video_creator',
                'description': """
                        将用户转移到 image_video_creator。关于此智能体：专门从事从文本提示或输入图像生成图像和视频。
                        """
            }
        ]

        super().__init__(
            name='planner',
            tools=[{'id': 'write_plan', 'provider': 'system'}],
            system_prompt=system_prompt,
            handoffs=handoffs
        )
