"""视频提示词拼装：按品类（火锅 / 奶茶 / 通用）组合正向与负向约束；
也可通过 Agnes 文本模型做 LLM 增强。
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from services.config_service import config_service
from tools.agnes_model_config import (
    AGNES_TEXT_MODEL_DEFAULT,
    AGNES_TEXT_MODELS,
    AGNES_VISION_MODEL,
)

# --- 正向 / 负向约束素材 ---

GENERIC_FOOD_POSITIVE_CONSTRAINTS = [
    "新鲜食材的自然色泽变化",
    "食材比例真实的餐饮摆盘",
]

HOTPOT_FOOD_POSITIVE_CONSTRAINTS = [
    "薄切肥牛卷上可见清晰肉纹和油花",
    "红油汤底表面漂浮辣椒油和气泡",
    "新鲜切好配菜的自然色泽变化",
    "正宗中式火锅用餐场景",
    "火锅上方自然升腾的热气",
]

FOOD_NEGATIVE_CONSTRAINTS = [
    "变形食物",
    "塑料质感",
    "蜡质食物",
    "橡胶质感肉类",
    "光滑人工块状物",
    "扭曲变形的肉",
    "AI生成破损食物",
    "畸形食材",
    "毁容形状",
    "卡通风格食物",
    "抽象食物团块",
    "漂浮的食材",
    "变形的人手",
]

# 多视频时的两套风格标签
REALISTIC_STYLE_TAGS = [
    "纪录片手持拍摄风格",
    "手机实拍真实餐厅",
    "自然环境光",
    "真实自然的用餐瞬间",
]

DIGITAL_HUMAN_STYLE_TAGS = [
    "数字人元宇宙虚拟形象风格",
    "UE5超写实数字人服务员",
    "虚拟制片棚三点布光",
    "精致商业广告质感",
]

REALISTIC_NEGATIVE_TAGS = [
    "卡通",
    "动画",
    "插画",
    "绘画",
    "素描",
    "漫画",
    "动漫",
]

DIGITAL_HUMAN_NEGATIVE_TAGS = [
    "卡通",
    "动漫",
    "插画",
    "低多边形",
    "纪录片手持拍摄",
    "手机实拍",
    "抽象食物团块",
]

# 火锅：拼在 prompt 最前的硬规则
HOTPOT_CULINARY_PRIORITY = (
    "正宗四川火锅店场景。"
    "【重要】肉类必须是叠放在白色瓷盘上的薄切雪花肥牛卷，"
    "禁止厚肉片或生肉块直接入锅。"
    "【重要】蔬菜必须是后厨切好的小份配菜摆盘"
    "（摘好洗好的绿叶菜、金针菇束、豆腐块、莲藕片），"
    "禁止整根未处理的蔬菜或大块根茎。"
    "【重要】锅底为圆形不锈钢鸳鸯锅，中间有分隔："
    "一侧是翻滚的麻辣红汤，漂浮花椒和油花；"
    "另一侧是清汤；汤底必须冒泡升腾热气，"
    "禁止平坦的红色颜料或胶质静止液体"
)

HOTPOT_SCENE_CONSTRAINTS = [
    "穿制服的服务员将鸳鸯锅底端上木质餐桌",
    "食客用筷子夹薄肉片涮入翻滚汤底",
    "热闹拥挤的用餐大厅，暖色吊灯，人流自然穿梭",
    "抖音风格短视频火锅店叙事",
]

# 非火锅场景追加，避免串成火锅
NON_HOTPOT_NEGATIVE_CONSTRAINTS = [
    "火锅",
    "锅底",
    "鸳鸯锅",
    "红油汤底",
    "涮肉",
    "九宫格",
    "麻辣锅",
    "hotpot",
    "hot pot",
]

HOTPOT_NEGATIVE_CONSTRAINTS = [
    "整根未切蔬菜",
    "未修剪的菜梗",
    "大块生根茎",
    "厚矩形肉块",
    "汤中漂浮生肉块",
    "未切片的块状肉",
    "抽象食物团块",
    "平坦红色颜料状汤底",
    "无气泡的胶质静止汤底",
    "无分隔的单色汤底",
    "无鸳鸯分隔的错误锅型",
    "塑料质感汤底",
    "食物中随机木棍",
    "变形人手",
    "漂浮食材",
    "不真实汤底质感",
    "畸形食材形状",
]

# 奶茶：虚构品牌、封口一致、少拍坏手
MILK_TEA_CULINARY_PRIORITY = (
    "现代简约风奶茶店场景。"
    "【重要】全片必须是同一家虚构品牌门店，装修、制服、杯型、杯身logo全程一致，"
    "禁止中途切换成空店棚拍或另一家店。"
    "【重要】禁止出现任何真实奶茶品牌及其logo，"
    "尤其禁止喜茶、Heytea、奈雪、茶百道、蜜雪冰城、一点点、COCO、瑞幸、星巴克"
    "以及喜茶经典侧脸喝饮线稿logo；"
    "若需品牌元素，仅使用简洁圆形自有logo（如单个英文字母），"
    "门店招牌可用简短英文店名；菜单/海报/工牌尽量用图案代替文字，禁止乱码。"
    "【重要】产品为透明塑料杯珍珠奶茶：底部黑珍珠自然错落堆叠（禁止整齐网格排列），"
    "中间奶茶色泽自然分层，倒茶液体呈自然水流而非丝带状固体，"
    "顶部芝士奶盖或奶油顶，杯壁有冷凝水；"
    "禁止蜡质/塑料感饮品、畸形杯体、鬼影叠加logo、漂浮杯盖。"
    "【重要】封口方式与杯盖必须匹配，全片只选一种且保持一致："
    "方案A（膜封）：画面出现封口机时，杯口必须是热封薄膜封口，禁止再出现可拆塑料平盖或球盖；"
    "方案B（手扣盖）：芝士奶盖/奶油高顶产品用手扣球盖或平盖，画面中禁止出现膜封机；"
    "禁止封口机与塑料杯盖同时出现，禁止高奶盖产品却用膜封压平。"
    "【重要】尽量少拍握杯手部超特写；优先产品居中、店员半身/侧面出镜，手部虚化或出画；"
    "若出现手部，必须五指完整、关节清晰、不粘连、不融化、不穿模。"
    "【重要】禁止出现手指没有触碰到杯子的时候，杯子就自己移动的情况"
    "【重要】禁止出现一个视频中人物既有真人也有仿真人"
    "镜头不能晃动太快，并且不能穿帮，例如在一个门店镜头不能从客户直接到店员制作的地方，这样会穿帮"
)

MILK_TEA_FOOD_POSITIVE_CONSTRAINTS = [
    "杯壁自然冷凝水珠",
    "底部黑珍珠自然错落堆叠",
    "芝士奶盖层厚实平整",
    "倒茶水流自然真实",
    "封口方式与杯盖匹配一致",
    "奶茶色泽诱人且分层真实",
    "产品特写时背景仍有虚化人流",
    "同一门店制服与杯型全程一致",
]

MILK_TEA_NEGATIVE_CONSTRAINTS = [
    "喜茶",
    "Heytea",
    "HEYTEA",
    "奈雪",
    "茶百道",
    "蜜雪冰城",
    "一点点",
    "COCO都可",
    "真实品牌logo",
    "侧脸喝饮线稿logo",
    "乱码文字",
    "菜单乱码",
    "海报乱码",
    "工牌乱码",
    "鬼影叠加logo",
    "变形人手",
    "粘连手指",
    "多余手指",
    "融化手部",
    "手指穿模",
    "握杯手部超特写",
    "漂浮杯子",
    "漂浮杯盖",
    "丝带状倒茶液体",
    "珍珠整齐网格排列",
    "封口机与塑料杯盖同时出现",
    "膜封机配球盖",
    "膜封机配平盖",
    "高奶盖却膜封压平",
    "封口方式中途切换",
    "蜡质饮品",
    "塑料质感奶茶",
    "畸形杯体",
    "空旷无人门店",
    "棚拍空背景",
    "特写时背景无人",
    "中途切换门店装修",
]

# 预留，主流程暂未注入
POULTRY_POSITIVE_CONSTRAINTS = [
    "标准鸡翅形状",
    "酥脆自然表皮",
    "自然酱汁质感",
    "无尖锐凸起",
    "真实禽类结构",
]

POULTRY_NEGATIVE_CONSTRAINTS = [
    "变形鸡肉",
    "尖锐凸起表皮",
    "怪异尖刺质感",
    "扭曲肉类",
    "AI生成破损食物",
    "不真实凹凸皮肤",
    "丑陋块状物",
]

ASPECT_RATIO_PROMPT_HINTS = {
    "9:16": "竖屏视频，9:16比例，移动端构图",
    "16:9": "横屏视频，16:9比例，宽银幕构图",
    "1:1": "正方形视频，1:1比例",
    "4:3": "4:3比例视频",
    "3:4": "竖屏3:4比例视频",
    "21:9": "超宽电影感视频，21:9比例",
}


def append_aspect_ratio_hint(prompt: str, aspect_ratio: str) -> str:
    """追加画幅提示；已存在则不重复。"""
    hint = ASPECT_RATIO_PROMPT_HINTS.get(aspect_ratio)
    if not hint or hint in prompt:
        return prompt
    return f"{prompt}，{hint}"


def is_hotpot_scene(prompt: str) -> bool:
    """关键词判定是否火锅场景。"""
    lowered = prompt.lower()
    keywords = (
        "hotpot", "hot pot", "火锅", "锅底", "麻辣", "红油", "鸳鸯锅",
        "火锅店", "火锅底", "九宫格", "涮肉", "毛肚", "肥牛",
        "yin-yang", "spicy broth", "chili oil broth", "pot base",
        "waiter carrying", "端锅底", "服务员端",
    )
    return any(keyword in lowered for keyword in keywords)


def is_milk_tea_scene(prompt: str) -> bool:
    """关键词判定是否奶茶/茶饮场景。"""
    lowered = prompt.lower()
    keywords = (
        "奶茶", "珍珠奶茶", "波霸", "奶盖", "芝士奶盖", "摇茶", "封口机",
        "奶茶店", "茶饮店", "手打柠檬茶", "果茶", "芋泥", "椰果",
        "boba", "bubble tea", "milk tea", "milktea", "brown sugar pearl",
        "tapioca", "cheese foam", "heytea", "喜茶", "咖啡", "咖啡馆", "咖啡店", "咖啡师", "手冲", "意式", "拿铁", "美式",
    )
    # 只要里面任意一个结果为 True，整体返回 True；全部都是 False 才返回 False
    return any(keyword in lowered for keyword in keywords)


def build_scene_prompt(
    scene_prompt: str,
    camera_motion: str = "",
    lighting: str = "",
    scene: str = "",
    has_reference_image: bool = False,
    style_tags: list | None = None,
    negative_tags: list | None = None,
    include_hotpot_constraints: bool = False,
    include_milk_tea_constraints: bool = False,
) -> dict:
    """
    拼装单条 prompt / negative_prompt。

    正向顺序：品类硬规则 → 用户描述 → 场景约束 → scene/运镜/灯光 → style_tags → 食物正向。
    火锅与奶茶约束互斥；返回 {"prompt", "negative_prompt"}。
    """
    layers = []

    if include_hotpot_constraints:
        layers.append(HOTPOT_CULINARY_PRIORITY)
    elif include_milk_tea_constraints:
        layers.append(MILK_TEA_CULINARY_PRIORITY)

    if scene_prompt:
        layers.append(scene_prompt)

    if include_hotpot_constraints:
        layers.extend(HOTPOT_SCENE_CONSTRAINTS)
    elif include_milk_tea_constraints:
        layers.extend(MILK_TEA_SCENE_CONSTRAINTS)

    if scene:
        layers.append(scene)

    if camera_motion:
        layers.append(camera_motion)

    if lighting:
        layers.append(lighting)

    if style_tags:
        layers.extend(style_tags)

    if include_hotpot_constraints:
        layers.extend(HOTPOT_FOOD_POSITIVE_CONSTRAINTS)
    elif include_milk_tea_constraints:
        layers.extend(MILK_TEA_FOOD_POSITIVE_CONSTRAINTS)
    else:
        layers.extend(GENERIC_FOOD_POSITIVE_CONSTRAINTS)

    prompt = "，".join(layer for layer in layers if layer)

    if has_reference_image:
        prompt += "，强烈参考所提供图片的形状和质感，参考权重0.85"

    negative_prompt = "，".join(FOOD_NEGATIVE_CONSTRAINTS)
    if include_hotpot_constraints:
        negative_prompt += "，" + "，".join(HOTPOT_NEGATIVE_CONSTRAINTS)
    elif include_milk_tea_constraints:
        negative_prompt += "，" + "，".join(MILK_TEA_NEGATIVE_CONSTRAINTS)
        negative_prompt += "，" + "，".join(NON_HOTPOT_NEGATIVE_CONSTRAINTS)
    else:
        negative_prompt += "，" + "，".join(NON_HOTPOT_NEGATIVE_CONSTRAINTS)
    if negative_tags:
        negative_prompt += "，" + "，".join(negative_tags)

    return {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
    }


def build_multi_video_prompts(
    scene_prompt: str,
    quantity: int = 1,
    aspect_ratio: str = "9:16",
    has_reference_image: bool = False,
    is_hotpot: bool | None = None,
    is_milk_tea: bool | None = None,
) -> list[dict]:
    """
    生成 1～2 条提示词。quantity>=2 时最多两条：写实 + 仿真人。
    is_hotpot / is_milk_tea 为 None 时自动检测；火锅优先于奶茶。
    """
    prompts = []
    include_hotpot = is_hotpot if is_hotpot is not None else is_hotpot_scene(scene_prompt)
    include_milk_tea = (
        False if include_hotpot
        else (is_milk_tea if is_milk_tea is not None else is_milk_tea_scene(scene_prompt))
    )

    if quantity == 1:
        if include_hotpot:
            camera_motion = "镜头在餐厅场景中自然移动"
            lighting = "温暖电影感灯光，食物高光诱人"
            scene = "真实用餐氛围，顾客自然走动"
        elif include_milk_tea:
            camera_motion = "手持镜头穿过排队过道，再跟拍店员半身制作，最后推进产品特写；"
            lighting = "明亮干净的店内灯光与自然窗光，杯身与奶盖高光诱人"
            scene = (
                "同一奶茶门店全程高人气；开篇排队清晰，中段吧台忙碌，"
                "结尾产品特写背景仍保留虚化顾客或店员，热闹感不掉档"
            )
        else:
            camera_motion = "镜头在门店场景中自然移动"
            lighting = "温暖电影感灯光，产品高光诱人"
            scene = "真实门店氛围，顾客自然走动，高人气忙碌感"
        result = build_scene_prompt(
            scene_prompt=scene_prompt,
            camera_motion=camera_motion,
            lighting=lighting,
            scene=scene,
            has_reference_image=has_reference_image,
            include_hotpot_constraints=include_hotpot,
            include_milk_tea_constraints=include_milk_tea,
        )
        result["ratio"] = aspect_ratio
        prompts.append(result)

    elif quantity >= 2:
        if include_hotpot:
            styles = [
                {
                    "name": "写实风格",
                    "camera_motion": "手持镜头穿过拥挤过道，跟随服务员端锅底",
                    "lighting": "暖色吊灯与自然窗光，纪录片写实感",
                    "scene": "开放式现实场景，画面环境、人物互动可自由创作，包含商品特写镜头",
                    "style_tags": REALISTIC_STYLE_TAGS,
                    "negative_tags": REALISTIC_NEGATIVE_TAGS,
                },
                {
                    "name": "仿真人风格",
                    "camera_motion": "平滑电影级轨道镜头，数字人服务员端锅走向餐桌",
                    "lighting": "棚拍三点布光，精致商业调色，浅景深",
                    "scene": "开放式现实场景，画面环境、人物互动可自由创作，包含商品特写镜头",
                    "style_tags": DIGITAL_HUMAN_STYLE_TAGS,
                    "negative_tags": DIGITAL_HUMAN_NEGATIVE_TAGS,
                },
            ]
        elif include_milk_tea:
            styles = [
                {
                    "name": "写实风格",
                    "camera_motion": "手持镜头穿过排队过道，跟拍店员半身制作",
                    "lighting": "明亮店内灯光与自然窗光，纪录片写实感",
                    "scene": "开放式现实场景，画面环境、人物互动可自由创作，包含商品特写镜头",
                    "style_tags": REALISTIC_STYLE_TAGS,
                    "negative_tags": REALISTIC_NEGATIVE_TAGS,
                },
                {
                    "name": "仿真人风格",
                    "camera_motion": "结尾产品特写手部出画或虚化",
                    "lighting": "棚拍三点布光，精致商业调色，浅景深",
                    "scene": "开放式现实场景，画面环境、人物互动可自由创作，包含商品特写镜头",
                    "style_tags": DIGITAL_HUMAN_STYLE_TAGS,
                    "negative_tags": DIGITAL_HUMAN_NEGATIVE_TAGS,
                },
            ]
        else:
            styles = [
                {
                    "name": "写实风格",
                    "camera_motion": "手持镜头穿过拥挤过道，跟随店员忙碌服务",
                    "lighting": "暖色店内灯光与自然窗光，纪录片写实感",
                    "scene": "开放式现实场景，画面环境、人物互动可自由创作，包含商品特写镜头",
                    "style_tags": REALISTIC_STYLE_TAGS,
                    "negative_tags": REALISTIC_NEGATIVE_TAGS,
                },
                {
                    "name": "仿真人风格",
                    "camera_motion": "平滑电影级轨道镜头，数字人店员展示产品并服务顾客",
                    "lighting": "棚拍三点布光，精致商业调色，浅景深",
                    "scene": "开放式现实场景，画面环境、人物互动可自由创作，包含商品特写镜头",
                    "style_tags": DIGITAL_HUMAN_STYLE_TAGS,
                    "negative_tags": DIGITAL_HUMAN_NEGATIVE_TAGS,
                },
            ]
        for i in range(min(quantity, 2)):
            style = styles[i]
            result = build_scene_prompt(
                scene_prompt=scene_prompt,
                camera_motion=style["camera_motion"],
                lighting=style["lighting"],
                scene=style["scene"],
                has_reference_image=has_reference_image,
                style_tags=style["style_tags"],
                negative_tags=style["negative_tags"],
                include_hotpot_constraints=include_hotpot,
                include_milk_tea_constraints=include_milk_tea,
            )
            result["prompt"] += "，若是场景切换，请使用合适的运镜，并保持场景的连贯性，避免生硬切换"
            result["ratio"] = aspect_ratio
            result["style_name"] = style["name"]
            prompts.append(result)
    return prompts


def enhance_video_prompt(
    original_prompt: str,
    aspect_ratio: str = "9:16",
    has_reference_image: bool = False,
    quantity: int = 1,
    user_context: str = "",
) -> dict:
    """
    对外入口。quantity>1 返回 {"prompts", "ratio"}，否则返回单条 dict。
    品类检测会合并 user_context；火锅优先于奶茶。
    """
    scene_prompt = original_prompt.strip()
    if not scene_prompt:
        scene_prompt = "精美食物场景"

    combined_context = f"{scene_prompt} {user_context}".strip()
    include_hotpot = is_hotpot_scene(combined_context)
    include_milk_tea = (not include_hotpot) and is_milk_tea_scene(combined_context)

    if quantity > 1:
        prompts = build_multi_video_prompts(
            scene_prompt=scene_prompt,
            quantity=quantity,
            aspect_ratio=aspect_ratio,
            has_reference_image=has_reference_image,
            is_hotpot=include_hotpot,
            is_milk_tea=include_milk_tea,
        )
        for item in prompts:
            item["prompt"] = append_aspect_ratio_hint(item["prompt"], aspect_ratio)
        return {
            "prompts": prompts,
            "ratio": aspect_ratio,
        }

    if include_hotpot:
        camera_motion = "镜头在餐厅场景中自然移动"
        lighting = "温暖电影感灯光，食物高光诱人"
        scene = "真实用餐氛围，顾客自然走动"
    elif include_milk_tea:
        camera_motion = "手持镜头穿过排队过道，再跟拍店员半身制作，最后推进产品特写；"
        lighting = "明亮干净的店内灯光与自然窗光，杯身与奶盖高光诱人"
        scene = (
            "同一奶茶门店全程高人气；开篇排队清晰，中段吧台忙碌，"
            "结尾产品特写背景仍保留虚化顾客或店员，热闹感不掉档"
        )
    else:
        camera_motion = "镜头在门店场景中自然移动"
        lighting = "温暖电影感灯光，产品高光诱人"
        scene = "真实门店氛围，顾客自然走动，高人气忙碌感"

    result = build_scene_prompt(
        scene_prompt=scene_prompt,
        camera_motion=camera_motion,
        lighting=lighting,
        scene=scene,
        has_reference_image=has_reference_image,
        include_hotpot_constraints=include_hotpot,
        include_milk_tea_constraints=include_milk_tea,
    )
    result["prompt"] = append_aspect_ratio_hint(result["prompt"], aspect_ratio)
    result["ratio"] = aspect_ratio
    return result


# ---------------------------------------------------------------------------
# LLM 增强：Agnes 2.5 Flash
# ---------------------------------------------------------------------------

# 可拼进最终视频 prompt 的画面约束（给生成模型看）
_VIDEO_PROMPT_APPEND_CONSTRAINTS = (
    "严格匹配用户品类，禁止擅自改成其他品类；"
    "禁止出现瑞幸、星巴克、喜茶、奈雪等真实连锁品牌及其logo；"
    "画面为中文商业短视频质感；"
    "补全主体、产品特写、环境人流、运镜开篇到结尾、光线；"
    "少拍畸形人手，如果是饮品的话优先产品居中与半身店员、手部虚化，禁止杯口与人脸穿模；"
    "画面尽量减少入镜人手镜头，如果一定要有人物画面，只保留远景人物，避免手部特写/中景手部出镜"
    "冷热饮与蒸汽表现逻辑一致；"
    "咖啡类强调杯中液体油脂拉花或闻香，不要用珍珠奶茶杯型冒充咖啡；"
    "开场即出现产品或制作，避免无关空镜；"
    "场景切换时运镜自然连贯，避免生硬跳切；"
    "画面中文文字要清晰完整，无乱码、无畸形生僻字；"
    "画面中不能出现穿模的场景，比如杯子盖子突然消失。若画面出现喝饮，须用吸管或杯口自然饮用"
    "画面中至少七个分镜，但是画面中同一场景不能超过两个分镜"
    "画面中不要出现额外文字、乱码、畸形汉字、无法识别字符"
    "视频的节奏需要适中，不能太快，也不能太慢"
    "画面需要有特点，不能太平淡，要让人有看下去的欲望"
    "背景音乐需要符合视频的氛围，不能太吵闹，也不能太安静，也需要适用于宣传片的背景音乐"
    "切镜了不要快速晃动镜头，也不要有多余的镜头，不要出现空镜"
    "人物要为健康合规人物形象"
    "若是热饮，盖子是盖住状态不能展现出热气腾腾的场景，这样是不符合生活场景的"
    "生成视频的时候，要避免文字招牌；视频人物长相不能太像，需要区别一下"
    "在视频中，同一人物穿衣不能变，不能出现变装"
    "在视频中的同一场景，原本是三个人的，不能后面又突然变成四个人，例如提示词说三个人在一起吃小龙虾，就不能前面是三个人，后面变成四个人一起在吃"
)

# 双视频强制风格差异（写真 vs 仿真人），避免两条提示词几乎相同
_REALISTIC_STYLE_SUFFIX = (
    "【风格：写真写实】纪录片手持拍摄风格，手机实拍真实门店，自然环境光，"
    "真实顾客与店员，产品材质真实可触，禁止数字人、UE5虚拟形象、棚拍三点布光"
)
_DIGITAL_HUMAN_STYLE_SUFFIX = (
    "【风格：仿真人】数字人元宇宙虚拟形象风格，UE5超写实数字人店员与顾客，"
    "虚拟制片棚三点布光，精致商业广告质感，平滑电影级轨道镜头，"
    "禁止纪录片手持拍摄、手机实拍感"
)
_REALISTIC_NEGATIVE_EXTRA = "，".join(
    REALISTIC_NEGATIVE_TAGS + ["数字人", "UE5虚拟形象", "元宇宙虚拟形象", "棚拍三点布光"]
)
_DIGITAL_HUMAN_NEGATIVE_EXTRA = "，".join(
    DIGITAL_HUMAN_NEGATIVE_TAGS + ["手机实拍真实门店", "真实顾客抓拍"]
)

# 只给 LLM 的系统指令（含 JSON 格式，不要拼进视频 prompt）
_PROMPT_ENHANCE_SYSTEM = f"""你是短视频广告提示词专家，负责把用户的简短需求扩写成可直接用于文生视频的中文提示词。

硬性规则：
1. 严格保留用户品类与品牌意图：用户要咖啡就写咖啡店/咖啡产品，禁止改成奶茶、火锅或其他品类。
2. 禁止出现任何真实连锁品牌及其 logo（如瑞幸、星巴克、喜茶、奈雪、麦当劳等）。
3. 输出必须是中文；不要翻译成英文，画面中文文字要清晰完整，无乱码、无畸形生僻字。
4. 补全可拍细节：主体、产品特写、环境人流、运镜（开篇→中段→结尾）、光线、画幅。
5. 餐饮类额外注意：少拍畸形人手；饮品优先产品居中、半身店员、手部虚化；禁止杯口与人脸穿模；冷热饮与蒸汽表现要逻辑一致。
6. 咖啡类：强调杯中液体/油脂/拉花或闻香，不要用珍珠奶茶杯型冒充咖啡；新品名可用虚构简约 logo，不要乱码贴纸堆砌。
7. 叙事连贯：开场就要出现产品或制作，避免无关路人空镜。

当生成条数为 2 时，必须输出两条差异明显的提示词：
- 第1条 style_name=写实风格：写真写实、手持实拍、真实人物与门店
- 第2条 style_name=仿真人风格：UE5数字人、棚拍三点布光、商业广告质感
两条的运镜、灯光、人物类型必须明显不同，禁止只改一两个词后复用同一段文案。

增强后的正向提示词末尾可自然融入这些约束语义：{_VIDEO_PROMPT_APPEND_CONSTRAINTS}

只输出一个 JSON 对象，不要 markdown，不要解释。格式：
{{"prompt":"增强后的正向提示词","negative_prompt":"负面提示词，逗号分隔","style_name":"可选风格名"}}
若需要多条（用户要 2 个风格），输出：
{{"prompts":[{{"prompt":"...","negative_prompt":"...","style_name":"写实风格"}},{{"prompt":"...","negative_prompt":"...","style_name":"仿真人风格"}}]}}
"""


def _append_video_constraints(prompt: str) -> str:
    """把画面约束拼到增强后的提示词末尾（避免重复拼接）。"""
    text = (prompt or "").strip()
    if not text:
        return _VIDEO_PROMPT_APPEND_CONSTRAINTS
    if _VIDEO_PROMPT_APPEND_CONSTRAINTS in text:
        return text
    return f"{text}要求：{_VIDEO_PROMPT_APPEND_CONSTRAINTS}"


def _strip_style_markers(prompt: str) -> str:
    """去掉已有风格标记，避免重复叠加。"""
    text = prompt or ""
    patterns = [
        r"【风格：写真写实】[^，]*",
        r"【风格：仿真人】[^，]*",
        r"，?数字人元宇宙虚拟形象风格[^，]*",
        r"，?UE5超写实数字人[^，]*",
        r"，?虚拟制片棚三点布光[^，]*",
        r"，?精致商业广告质感",
        r"，?纪录片手持拍摄风格",
        r"，?手机实拍真实(?:餐厅|门店)",
        r"，?自然环境光",
        r"，?写真写实风格[^，]*",
        r"，?仿真人风格[^，]*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    text = re.sub(r"，{2,}", "，", text).strip("， ").strip()
    return text


def _merge_negative(*parts: str) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        for item in str(part or "").split("，"):
            token = item.strip()
            if token and token not in seen:
                seen.add(token)
                ordered.append(token)
    return "，".join(ordered)


def _build_dual_style_prompts(
    base_prompt: str,
    *,
    aspect_ratio: str,
    negative_prompt: str = "",
    second_prompt: str | None = None,
    second_negative: str | None = None,
) -> list[dict]:
    """生成写真写实 / 仿真人两条差异化提示词。"""
    base = _strip_style_markers(_append_video_constraints(base_prompt))
    second_base = _strip_style_markers(
        _append_video_constraints(second_prompt or base_prompt)
    )

    realistic_prompt = append_aspect_ratio_hint(
        f"{base}，{_REALISTIC_STYLE_SUFFIX}",
        aspect_ratio,
    )
    digital_prompt = append_aspect_ratio_hint(
        f"{second_base}，{_DIGITAL_HUMAN_STYLE_SUFFIX}",
        aspect_ratio,
    )

    return [
        {
            "prompt": realistic_prompt,
            "negative_prompt": _merge_negative(
                negative_prompt, _REALISTIC_NEGATIVE_EXTRA
            ),
            "ratio": aspect_ratio,
            "style_name": "写实风格",
        },
        {
            "prompt": digital_prompt,
            "negative_prompt": _merge_negative(
                second_negative if second_negative is not None else negative_prompt,
                _DIGITAL_HUMAN_NEGATIVE_EXTRA,
            ),
            "ratio": aspect_ratio,
            "style_name": "仿真人风格",
        },
    ]


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("模型未返回可解析的 JSON")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("模型返回的 JSON 不是对象")
    return data


async def _call_agnes_chat(
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    preferred_models: list[str] | None = None,
) -> str:
    """调用 Agnes Chat Completions，主模型失败时降级备用文本模型。"""
    agnes_cfg = config_service.app_config.get("agnes", {}) or {}
    api_key = (agnes_cfg.get("api_key") or "").strip()
    base_url = (agnes_cfg.get("url") or "").rstrip("/")
    if not api_key or not base_url:
        raise ValueError("未配置 Agnes api_key 或 url")

    if preferred_models:
        models_to_try = list(preferred_models) + [
            m for m in AGNES_TEXT_MODELS if m not in preferred_models
        ]
    else:
        models_to_try = [AGNES_TEXT_MODEL_DEFAULT] + [
            m for m in AGNES_TEXT_MODELS if m != AGNES_TEXT_MODEL_DEFAULT
        ]
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=20.0)) as client:
        for model_name in models_to_try:
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            try:
                print(f"✍️ [PromptEnhance] 调用 Agnes 文本模型: {model_name}")
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Agnes chat HTTP {response.status_code}: {response.text[:300]}"
                    )
                body = response.json()
                content = (
                    body.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                if not content or not str(content).strip():
                    raise RuntimeError("Agnes chat 返回空内容")
                return str(content).strip()
            except Exception as exc:
                last_error = exc
                print(f"⚠️ [PromptEnhance] 模型 {model_name} 失败: {exc}")
                continue

    raise RuntimeError(f"Agnes 提示词增强失败: {last_error}")


def _shrink_data_url_for_vision(data_url: str, max_side: int = 1024) -> str:
    """缩小参考图，降低识图请求体积。"""
    try:
        import base64
        from io import BytesIO
        from PIL import Image

        if not data_url.startswith("data:") or "," not in data_url:
            return data_url
        header, b64 = data_url.split(",", 1)
        mime = "image/jpeg"
        if ";" in header:
            mime = header[5:].split(";")[0] or mime
        image = Image.open(BytesIO(base64.b64decode(b64)))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        w, h = image.size
        scale = min(1.0, float(max_side) / float(max(w, h)))
        if scale < 1.0:
            image = image.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=85)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as exc:
        print(f"⚠️ [PromptEnhance] 压缩参考图失败，使用原图: {exc}")
        return data_url


async def describe_reference_images_with_agnes(
    input_images: list[str] | None,
    *,
    max_images: int = 2,
) -> str:
    """
    用 agnes-2.0-flash 把参考图识别成中文文字描述。
    input_images 为 data URL 列表（与 process_input_image 输出一致）。
    """
    images = [img for img in (input_images or []) if img]
    if not images:
        return ""

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "请用中文详细描述图片中的产品、包装、颜色、材质、文字/logo、场景环境与构图重点。"
                "只输出客观画面描述，不要建议，不要 markdown。"
                "若有多张图，按顺序分别描述后合并为一段连贯文字。"
            ),
        }
    ]
    for data_url in images[:max_images]:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _shrink_data_url_for_vision(data_url)},
            }
        )

    try:
        caption = await _call_agnes_chat(
            [{"role": "user", "content": content}],
            temperature=0.2,
            max_tokens=800,
            preferred_models=[AGNES_VISION_MODEL],
        )
        caption = re.sub(r"\s+", " ", caption).strip()
        print(f"🖼️ [PromptEnhance] 参考图识别结果: {caption[:200]}...")
        return caption
    except Exception as exc:
        print(f"⚠️ [PromptEnhance] 参考图识别失败，跳过: {exc}")
        return ""


def _append_image_caption(prompt: str, caption: str) -> str:
    """把识图描述拼进最终提示词。"""
    text = (prompt or "").strip()
    desc = (caption or "").strip()
    if not desc:
        return text
    marker = f"参考图画面描述：{desc}"
    if desc in text or marker in text:
        return text
    if not text:
        return marker
    return f"{text}，{marker}"


async def enhance_video_prompt_with_agnes(
    original_prompt: str,
    aspect_ratio: str = "9:16",
    has_reference_image: bool = False,
    quantity: int = 1,
    user_context: str = "",
    input_images: list[str] | None = None,
) -> dict:
    """
    用 Agnes 增强用户提示词；若有上传图，先用 agnes-2.0-flash 识图再拼进最终提示词。
    成功时返回结构与 enhance_video_prompt 一致；失败则回退规则增强。
    """
    scene_prompt = (original_prompt or "").strip() or "精美产品宣传场景"
    qty = max(1, min(2, int(quantity or 1)))

    image_caption = ""
    if input_images or has_reference_image:
        image_caption = await describe_reference_images_with_agnes(input_images)

    user_parts = [
        f"用户需求：{scene_prompt}",
        f"画幅：{aspect_ratio}",
        f"生成条数：{qty}（1=单条；2=写实+仿真人两条）",
        f"是否有参考图：{'是' if (input_images or has_reference_image) else '否'}",
    ]
    if image_caption:
        user_parts.append(f"参考图画面描述：{image_caption}")
        user_parts.append("请把参考图中的产品外观、包装与关键视觉特征融入增强后的提示词。")
    if user_context.strip():
        user_parts.append("用户原始上下文：" + user_context.strip())
    user_parts.append("请按系统要求只输出 JSON。")

    try:
        raw = await _call_agnes_chat(
            [
                {"role": "system", "content": _PROMPT_ENHANCE_SYSTEM},
                {"role": "user", "content": "\n".join(user_parts)},
            ]
        )
        data = _extract_json_object(raw)

        if qty > 1:
            # 无论模型返回 1 条还是 2 条，都强制套写真 / 仿真人两套差异化风格
            items = data.get("prompts") if isinstance(data.get("prompts"), list) else []
            first_prompt = ""
            first_negative = str(data.get("negative_prompt") or "").strip()
            second_prompt = None
            second_negative = None

            if items:
                first = items[0] if isinstance(items[0], dict) else {}
                first_prompt = str(first.get("prompt") or "").strip()
                first_negative = str(
                    first.get("negative_prompt") or first_negative
                ).strip()
                if len(items) > 1 and isinstance(items[1], dict):
                    second_prompt = str(items[1].get("prompt") or "").strip() or None
                    second_negative = str(
                        items[1].get("negative_prompt") or ""
                    ).strip() or None

            if not first_prompt:
                first_prompt = str(data.get("prompt") or "").strip()

            if not first_prompt:
                raise ValueError("增强结果缺少 prompt 字段")

            dual = _build_dual_style_prompts(
                first_prompt,
                aspect_ratio=aspect_ratio,
                negative_prompt=first_negative,
                second_prompt=second_prompt,
                second_negative=second_negative,
            )
            for item in dual:
                item["prompt"] = _append_image_caption(item["prompt"], image_caption)
            return {"prompts": dual, "ratio": aspect_ratio}

        raw_prompt = str(data.get("prompt") or "").strip()
        if not raw_prompt and isinstance(data.get("prompts"), list) and data["prompts"]:
            first = data["prompts"][0]
            if isinstance(first, dict):
                raw_prompt = str(first.get("prompt") or "").strip()

        if not raw_prompt:
            raise ValueError("增强结果缺少 prompt 字段")

        prompt_text = _append_image_caption(
            _append_video_constraints(raw_prompt),
            image_caption,
        )

        return {
            "prompt": append_aspect_ratio_hint(prompt_text, aspect_ratio),
            "negative_prompt": str(data.get("negative_prompt") or "").strip(),
            "ratio": aspect_ratio,
        }
    except Exception as exc:
        print(f"⚠️ [PromptEnhance] LLM 增强失败，回退规则增强: {exc}")
        fallback = enhance_video_prompt(
            original_prompt=scene_prompt,
            aspect_ratio=aspect_ratio,
            has_reference_image=has_reference_image or bool(input_images),
            quantity=qty,
            user_context=user_context,
        )
        if image_caption:
            if fallback.get("prompts"):
                for item in fallback["prompts"]:
                    item["prompt"] = _append_image_caption(
                        item.get("prompt", ""), image_caption
                    )
            elif fallback.get("prompt"):
                fallback["prompt"] = _append_image_caption(
                    fallback["prompt"], image_caption
                )
        return fallback
