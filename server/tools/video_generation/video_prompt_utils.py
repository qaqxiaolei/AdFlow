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
    hint = ASPECT_RATIO_PROMPT_HINTS.get(aspect_ratio)
    if not hint or hint in prompt:
        return prompt
    return f"{prompt}，{hint}"


def is_hotpot_scene(prompt: str) -> bool:
    lowered = prompt.lower()
    keywords = (
        "hotpot", "hot pot", "火锅", "锅底", "麻辣", "红油", "鸳鸯锅",
        "火锅店", "火锅底", "九宫格", "涮肉", "毛肚", "肥牛",
        "yin-yang", "spicy broth", "chili oil broth", "pot base",
        "waiter carrying", "端锅底", "服务员端",
    )
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
) -> dict:
    layers = []

    if include_hotpot_constraints:
        layers.append(HOTPOT_CULINARY_PRIORITY)

    if scene_prompt:
        layers.append(scene_prompt)

    if include_hotpot_constraints:
        layers.extend(HOTPOT_SCENE_CONSTRAINTS)

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
    else:
        layers.extend(GENERIC_FOOD_POSITIVE_CONSTRAINTS)

    prompt = "，".join(layer for layer in layers if layer)

    if has_reference_image:
        prompt += "，强烈参考所提供图片的形状和质感，参考权重0.85"

    negative_prompt = "，".join(FOOD_NEGATIVE_CONSTRAINTS)
    if include_hotpot_constraints:
        negative_prompt += "，" + "，".join(HOTPOT_NEGATIVE_CONSTRAINTS)
    else:
        negative_prompt += "，" + "，".join(NON_HOTPOT_NEGATIVE_CONSTRAINTS)
    if negative_tags:
        negative_prompt += "，" + "，".join(negative_tags)

    return {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
    }


def build_food_prompt(
    main_ingredient: str,
    camera_motion: str = "",
    lighting: str = "",
    scene: str = "",
    has_reference_image: bool = False,
    style_tags: list = None,
    negative_tags: list = None,
) -> dict:
    return build_scene_prompt(
        scene_prompt=main_ingredient,
        camera_motion=camera_motion,
        lighting=lighting,
        scene=scene,
        has_reference_image=has_reference_image,
        style_tags=style_tags,
        negative_tags=negative_tags,
        include_hotpot_constraints=is_hotpot_scene(
            " ".join(filter(None, [main_ingredient, scene, camera_motion]))
        ),
    )


def build_multi_video_prompts(
    scene_prompt: str,
    quantity: int = 1,
    aspect_ratio: str = "9:16",
    has_reference_image: bool = False,
    is_hotpot: bool | None = None,
) -> list[dict]:
    prompts = []
    include_hotpot = is_hotpot if is_hotpot is not None else is_hotpot_scene(scene_prompt)

    if quantity == 1:
        if include_hotpot:
            camera_motion = "镜头在餐厅场景中自然移动"
            lighting = "温暖电影感灯光，食物高光诱人"
            scene = "真实用餐氛围，顾客自然走动"
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
                    "scene": "热闹真实的火锅店，木质餐桌，顾客用餐，可见蒸汽和翻滚汤底",
                    "style_tags": REALISTIC_STYLE_TAGS,
                    "negative_tags": REALISTIC_NEGATIVE_TAGS,
                },
                {
                    "name": "仿真人风格",
                    "camera_motion": "平滑电影级轨道镜头，数字人服务员端锅走向餐桌",
                    "lighting": "棚拍三点布光，精致商业调色，浅景深",
                    "scene": "虚拟制片火锅店场景，超写实数字人员工和顾客，高端广告质感",
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
                    "scene": "热闹真实的门店，顾客排队等候，店员忙碌制作，产品特写，高人气氛围",
                    "style_tags": REALISTIC_STYLE_TAGS,
                    "negative_tags": REALISTIC_NEGATIVE_TAGS,
                },
                {
                    "name": "仿真人风格",
                    "camera_motion": "平滑电影级轨道镜头，数字人店员展示产品并服务顾客",
                    "lighting": "棚拍三点布光，精致商业调色，浅景深",
                    "scene": "虚拟制片门店场景，超写实数字人员工和顾客，高端广告质感",
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
            )
            result["ratio"] = aspect_ratio
            result["style_name"] = style["name"]
            prompts.append(result)

    return prompts


def extract_main_ingredient(prompt: str) -> str:
    food_keywords = [
        "鸡", "牛", "猪", "羊", "鱼", "虾", "蔬菜",
        "面", "饭", "饺子", "汤", "咖喱", "牛排", "汉堡",
        "披萨", "意面", "沙拉", "三明治", "炸", "烤", "红烧",
        "炖", "寿司", "天妇罗", "拉面", "火锅", "菜",
        "鸡翅", "排骨", "肉", "豆腐", "蛋", "奶酪", "面包", "蛋糕",
        "冰淇淋", "甜品", "水果", "海鲜", "酱", "香料",
        "chicken", "beef", "pork", "hotpot", "meat", "tofu",
    ]

    lowered = prompt.lower()
    ingredients = []
    for keyword in food_keywords:
        if keyword in lowered and keyword not in ingredients:
            ingredients.append(keyword)

    if ingredients:
        return "，".join(ingredients[:3])

    return "精美食物场景"


def enhance_video_prompt(
    original_prompt: str,
    aspect_ratio: str = "9:16",
    has_reference_image: bool = False,
    quantity: int = 1,
    user_context: str = "",
) -> dict:
    scene_prompt = original_prompt.strip()
    if not scene_prompt:
        scene_prompt = "精美食物场景"

    combined_context = f"{scene_prompt} {user_context}".strip()
    include_hotpot = is_hotpot_scene(combined_context)

    if quantity > 1:
        prompts = build_multi_video_prompts(
            scene_prompt=scene_prompt,
            quantity=quantity,
            aspect_ratio=aspect_ratio,
            has_reference_image=has_reference_image,
            is_hotpot=include_hotpot,
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
    )
    result["prompt"] = append_aspect_ratio_hint(result["prompt"], aspect_ratio)
    result["ratio"] = aspect_ratio
    return result
