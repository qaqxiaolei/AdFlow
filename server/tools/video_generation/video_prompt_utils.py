FOOD_POSITIVE_CONSTRAINTS = [
    "standard food shape",
    "smooth natural texture",
    "natural sauce texture",
    "no sharp bump protrusions",
    "realistic food structure",
    "proper ingredient proportions",
    "authentic culinary presentation",
]

FOOD_NEGATIVE_CONSTRAINTS = [
    "deformed food",
    "sharp bump crust",
    "weird spike texture",
    "distorted meat",
    "AI broken food",
    "unrealistic bumpy skin",
    "ugly lumps",
    "malformed ingredients",
    "disfigured shape",
    "unnatural deformations",
    "cartoonish food",
    "pixelated food",
]

POULTRY_POSITIVE_CONSTRAINTS = [
    "standard chicken wing shape",
    "smooth crispy skin",
    "natural sauce texture",
    "no sharp bump protrusions",
    "realistic poultry structure",
]

POULTRY_NEGATIVE_CONSTRAINTS = [
    "deformed chicken",
    "sharp bump crust",
    "weird spike texture",
    "distorted meat",
    "AI broken food",
    "unrealistic bumpy skin",
    "ugly lumps",
]


def build_food_prompt(
    main_ingredient: str,
    camera_motion: str = "",
    lighting: str = "",
    scene: str = "",
    has_reference_image: bool = False,
) -> str:
    layers = []

    if main_ingredient:
        ingredient_layer = f"{main_ingredient}"
        if has_reference_image:
            ingredient_layer += ", strongly referencing the provided image for shape and texture"
        layers.append(ingredient_layer)

    if camera_motion:
        layers.append(camera_motion)

    if lighting:
        layers.append(lighting)

    if scene:
        layers.append(scene)

    layers.extend(FOOD_POSITIVE_CONSTRAINTS)

    prompt = ", ".join(layers)

    if has_reference_image:
        prompt += ", image reference weight 0.85"

    negative_prompt = ", ".join(FOOD_NEGATIVE_CONSTRAINTS)

    return {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
    }


def build_multi_video_prompts(
    main_ingredient: str,
    quantity: int = 1,
    aspect_ratio: str = "16:9",
    has_reference_image: bool = False,
) -> list[dict]:
    prompts = []

    if quantity == 1:
        camera_motion = "dynamic camera movement, slow pan around the dish"
        lighting = "warm cinematic lighting, appetizing highlights"
        scene = "professional food photography background, dark textured surface"

        result = build_food_prompt(
            main_ingredient=main_ingredient,
            camera_motion=camera_motion,
            lighting=lighting,
            scene=scene,
            has_reference_image=has_reference_image,
        )
        result["ratio"] = aspect_ratio
        prompts.append(result)

    elif quantity >= 2:
        camera_motions = [
            "dynamic handheld camera movement, close-up tracking shots around the dish",
            "slow cinematic zoom and pan, elegant circular motion",
        ]
        lightings = [
            "warm golden lighting from top-left, creating rich shadows",
            "soft diffused lighting with subtle backlight, clean bright aesthetic",
        ]
        scenes = [
            "rustic wooden table setting with fresh herbs and spices scattered",
            "modern minimalist slate plate on dark background with elegant garnishes",
        ]

        for i in range(min(quantity, 2)):
            result = build_food_prompt(
                main_ingredient=main_ingredient,
                camera_motion=camera_motions[i],
                lighting=lightings[i],
                scene=scenes[i],
                has_reference_image=has_reference_image,
            )
            result["ratio"] = aspect_ratio
            prompts.append(result)

    return prompts


def extract_main_ingredient(prompt: str) -> str:
    food_keywords = [
        "chicken", "beef", "pork", "lamb", "fish", "shrimp", "vegetable",
        "noodle", "rice", "dumpling", "soup", "curry", "steak", "burger",
        "pizza", "pasta", "salad", "sandwich", "fried", "grilled", "roasted",
        "braised", "stewed", "sushi", "tempura", "ramen", "hotpot", "dish",
        "wings", "ribs", "meat", "tofu", "egg", "cheese", "bread", "cake",
        "ice cream", "dessert", "fruit", "seafood", "sauce", "spice", "herb",
    ]

    words = prompt.lower().split()
    ingredients = []

    for word in words:
        cleaned_word = ''.join(c for c in word if c.isalnum())
        if cleaned_word in food_keywords and cleaned_word not in ingredients:
            ingredients.append(word)

    if ingredients:
        return ", ".join(ingredients[:3])

    return "delicious food"


def enhance_video_prompt(
    original_prompt: str,
    aspect_ratio: str = "16:9",
    has_reference_image: bool = False,
    quantity: int = 1,
) -> dict:
    main_ingredient = extract_main_ingredient(original_prompt)

    if quantity > 1:
        prompts = build_multi_video_prompts(
            main_ingredient=main_ingredient,
            quantity=quantity,
            aspect_ratio=aspect_ratio,
            has_reference_image=has_reference_image,
        )
        return {
            "prompts": prompts,
            "ratio": aspect_ratio,
        }
    else:
        result = build_food_prompt(
            main_ingredient=original_prompt,
            has_reference_image=has_reference_image,
        )
        result["ratio"] = aspect_ratio
        return result
