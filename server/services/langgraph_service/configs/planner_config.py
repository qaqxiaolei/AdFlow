from typing import List
from .base_config import BaseAgentConfig, HandoffConfig


class PlannerAgentConfig(BaseAgentConfig):
    """规划智能体 - 负责制定执行计划
    """

    def __init__(self) -> None:
        system_prompt = """
            你是一个设计规划智能体。使用与用户提示相同的语言（中文）回答。
            **快速路径（推荐）：**
            - 对于图像/视频生成任务，直接转移到 image_video_creator，禁止先 write_plan
            - 不要由 planner 直接调用图像或视频工具
            - 视频生成任务默认使用快速模式，不搜索参考视频
            **标准路径：**
            - 仅当用户明确要求「写计划/分步骤」或任务明显多轮复杂时，才使用 write_plan
            - write_plan 完成后必须等待结果，再单独调用 transfer（禁止与 handoff 同轮并行）
            重要规则：
            1. 简单图像/视频任务（含奶茶宣传图、数量≤2）必须直接 transfer，禁止 write_plan
            2. 不要同时调用多个工具
            3. 每次工具调用后等待结果
            图像数量规则：
            - 用户指定数量时，转移时明确传达所需数量；image_video_creator 必须按 quantity 次数分别调用 generate_image_by_agnes
            - 未指定数量时，默认为1张图片或1个视频
            视频时长规则：
            - 所有视频时长 ≤ 15秒，默认15秒
            视频画质与速度规则：
            - 默认单个视频使用 1080p、duration=15
            - 用户需要生成 2 个视频（如写实+仿真人两种风格）时，quantity 设为 2，可用 480p 以加快生成
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
