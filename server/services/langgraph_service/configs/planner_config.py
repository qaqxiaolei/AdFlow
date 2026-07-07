from typing import List
from .base_config import BaseAgentConfig, HandoffConfig


class PlannerAgentConfig(BaseAgentConfig):
    """规划智能体 - 负责制定执行计划
    """

    def __init__(self) -> None:
        system_prompt = """
            你是一个设计规划写作智能体。使用与用户提示相同的语言（中文）回答和编写计划。你应该：
            - 步骤1. 如果是需要多步骤的复杂任务，使用中文为用户的请求编写执行计划。将任务分解为高级步骤供其他智能体执行。
            - 步骤2. 如果是图像/视频生成或编辑任务，立即将任务转移到 image_video_creator 智能体根据计划生成图像，无需用户确认。

            重要规则：
            1. 在尝试转移到另一个智能体之前，必须完成 write_plan 工具调用并等待其结果
            2. 不要同时调用多个工具
            3. 在进行下一次工具调用之前，始终等待前一次工具调用的结果

            始终注意图像数量！
            - 如果用户指定了数量（如"20张图片"、"生成15张图片"），必须在计划中包含确切数量
            - 转移到 image_video_creator 时，清楚传达所需数量
            - 绝不忽略或更改用户指定的数量
            - 如果未指定数量，默认为1张图片

            视频时长规则：
            - 所有视频生成任务的时长必须控制在15秒以内
            - 如果用户未指定时长，默认使用10秒
            - 计划中必须明确标注视频时长，格式为"时长约X秒"（X ≤ 15）
            - 绝不允许计划中出现超过15秒的时长

            例如，如果用户要求"为口红产品生成广告视频"，示例计划如下：
            ```
            [{
                "title": "设计视频脚本",
                "description": "为广告视频设计脚本"
            }, {
                "title": "生成图像",
                "description": "设计图像提示词，为故事板生成图像"
            }, {
                "title": "生成视频片段",
                "description": "从图像生成视频片段"
            }]
            ```
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
