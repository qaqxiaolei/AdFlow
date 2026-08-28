"""图片提示词增强模块。

在用户原文后追加一套通用画面约束，减轻宣传图常见问题：
乱码文字、假品牌、左右拼图、缺少留白等。
由 generate_image_with_provider / generate_image_by_agnes 调用。
"""

from __future__ import annotations

import re
from typing import List

# ---------------------------------------------------------------------------
# 通用约束：所有生图统一追加，不再按品类分支
# ---------------------------------------------------------------------------

UNIVERSAL_IMAGE_CONSTRAINTS = (
    "【画面质量】高清商业摄影，主体清晰、构图稳定，适合宣传投放。"
    "【单图完整性】必须是一张独立完整的画面，只有一个主产品/主体；"
    "严禁左右分栏、拼贴对比图、一张图放两种风格。"
    "【品牌与文字】禁止画面内出现任何可读文字、乱码汉字、假品牌名、水印；"
    "禁止瑞幸、星巴克、喜茶、奈雪等真实连锁品牌及其 logo；"
    "若需品牌感，仅用简洁无文字的几何图形或留白，供后期自行添加 Logo/文案。"
    "【留白】主体周围或画面一侧预留干净空白区域，便于后期排版。"
    "【人物】若出现人物，仅作虚化背景氛围，面部不可清晰可辨，禁止畸形手脚。"
    "【整洁】台面/场景干净，避免杂物堆砌；道具须与产品本身逻辑一致。"
    "图片物品旁边的杂物必须要和物体本身有关联，例如生成的图片是珍珠奶茶，旁边的杂物就不应该有猕猴桃、橙子、草莓等其他水果。"
)

# 多图时的风格标签（写实 / 创意）；各对应一张完整单图
IMAGE_STYLE_A = (
    "【风格·写实】单张完整画面，仅一个产品主体居中；"
    "真实商业摄影/纪实质感，自然光或真实环境光，材质与细节可信；"
    "禁止左右分屏、禁止一张图里并排两款产品。"
)

IMAGE_STYLE_B = (
    "【风格·创意】单张完整画面，仅一个产品主体居中；"
    "更具设计感的构图与光色，视觉记忆点强，可适度艺术化但仍清晰可辨主体；"
    "禁止左右分屏、禁止一张图里并排两款产品，禁止乱码招牌文字。"
)

# 前端会在用户文案后插入 <aspect_ratio>、<quantity> 等标签，生图前需剥掉
_CONTROL_TAG_RE = re.compile(
    r"<(aspect_ratio|quantity|generation_mode|input_images)\b[^>]*>.*?</\1>\s*",
    re.IGNORECASE | re.DOTALL,
)
_SELF_CLOSING_CONTROL_RE = re.compile(
    r"<(aspect_ratio|quantity|generation_mode)\b[^>]*/?>\s*",
    re.IGNORECASE,
)


def strip_image_control_tags(prompt: str) -> str:
    """去掉前端注入的控制标签，避免这些 XML 片段写进生图模型。"""
    cleaned = _CONTROL_TAG_RE.sub("", prompt or "")
    cleaned = _SELF_CLOSING_CONTROL_RE.sub("", cleaned)
    return cleaned.strip()


def enhance_image_prompt(prompt: str) -> str:
    """
    增强单张图的提示词：保留用户原文，统一追加通用约束。

    已含「【画面质量】」时视为已增强过，直接返回，避免重复叠词。
    """
    base = strip_image_control_tags(prompt)
    if not base:
        base = "精美商业产品宣传图"

    # 已增强过则不再加工（例如上游已拼好风格后再传入）
    if "【画面质量】" in base:
        return base

    return f"{base}\n{UNIVERSAL_IMAGE_CONSTRAINTS}"


def build_multi_image_prompts(prompt: str, quantity: int = 1) -> List[str]:
    """
    按数量构造多条独立提示词（工具侧备用；Agent 侧也可自行分两次调用）。

    - quantity=1：返回 1 条增强后的提示词
    - quantity>=2：返回 2 条（写实 + 创意），各自一张完整单图，不做拼图
    """
    qty = max(1, min(2, int(quantity or 1)))
    base = strip_image_control_tags(prompt)
    if not base:
        base = "精美商业产品宣传图"

    if qty == 1:
        return [enhance_image_prompt(base)]

    return [
        enhance_image_prompt(f"{base}\n{IMAGE_STYLE_A}"),
        enhance_image_prompt(f"{base}\n{IMAGE_STYLE_B}"),
    ]
