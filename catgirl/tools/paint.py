# -*- coding: utf-8 -*-
"""
Gemini 3.1 Flash Image AI 绘图生成模块
支持利用 gemini-3.1-flash-image 绘制高质量插画、二次元、写实场景与艺术图
内置：
1. 1 分钟 8 张滑动窗口保护 (每次并发抽选 2 张候选图供视觉自检比选)
2. 多人动作与解剖防崩结构锚点 (坚决杜绝三只手、肢体错乱、多余手指、面部融化)
3. 动态姿势库与电影级场景扩展
4. 参考图背景绝对隔离
"""

import re
import json
import random
import asyncio
from typing import Tuple, List, Optional
import httpx

from ..config import API_KEY, BASE_URL, IMAGE_GEN_MODEL, IMAGE_GEN_CANDIDATES
from ..limiter import image_limiter

# 多人互动与解剖防崩结构锚点 (Danbooru 级防肢体融化、防三只手、防脸部畸变规范)
MULTI_PERSON_ANATOMY_ANCHORS = (
    "CRITICAL MULTI-CHARACTER, PROPS & COMPOSITION ANCHORS: "
    "- Distinct individual characters: clear separation between all characters, correct number of people as requested. "
    "- Anatomical correctness: each character has strictly two arms, two hands, and exactly five fingers per hand. "
    "- STRICTLY NO extra arms, NO extra hands, NO floating limbs, NO fused bodies, NO mutated or deformed fingers. "
    "- SPORTS & BALL GAMES LOGIC: EXACTLY ONE BALL ONLY IN THE ENTIRE SCENE (STRICTLY NO duplicate balls, NO multiple volleyballs/footballs/basketballs). All characters must interact with the SAME single ball! "
    "- For kissing or intimate embrace: side profile view or clean three-quarter profile shot, clear facial boundary lines, lips touching clearly without facial melting. "
    "- Dynamic physics: realistic sand splashing, water droplets, and authentic sports interaction."
)

# 动态姿势分类库
THEMATIC_POSES = {
    "cute_casual": [
        "leaning forward playfully with one hand reaching out toward viewer with open palm, gentle head tilt, dynamic foreshortening, intimate connection",
        "sitting comfortably on a scenic balustrade or stone ledge, dangling legs with one knee raised, relaxed natural posture, tilting head upward to the sky",
        "playful cute gesture with one hand making a soft cat paw or gentle peace sign near cheek, slight playful wink, expressive radiant face",
        "holding a small delicious pastry or sweet drink with both hands, taking a tiny cute bite with softly blushing cheeks, charming candid moment",
        "gentle morning stretch with arms raised overhead, arching back slightly, soft warm smile, casual cozy atmosphere",
        "resting chin in hands while leaning across a wooden tabletop, looking up with curious twinkling eyes and soft smile",
        "holding a fluffy cat or mascot plushie close to chest, nuzzling face into it with a sweet contented grin",
        "tucking a soft stray strand of hair behind ear, looking directly into camera with shy blushing smile, intimate framing"
    ],
    "dynamic_action": [
        "dynamic combat action stance with glowing energy particles swirling around hands, dramatic low angle shot, hair billowing with motion blur",
        "turning back mid-motion to look over shoulder with a radiant determined expression, running turn, dynamic hair and skirt fluttering in the wind",
        "drawing sword from scabbard with crisp diagonal motion, blade catching a brilliant gleam of light, sharp focused gaze",
        "mid-air acrobatic leap, one leg extended and ribbons spiraling outward, dynamic diagonal camera framing",
        "landing from a jump with one hand touching the ground, shockwave energy ripples expanding beneath feet, dramatic foreshortening",
        "casting an intricate glowing magic circle in front of hands, concentrated magic glow illuminating face in sharp contrast",
        "holding weapons ready at side, turning sharply with motion blur, fierce intense eyes, dynamic perspective"
    ],
    "dreamy_poetic": [
        "floating weightlessly in mid-air in zero gravity, legs slightly curved in elegant flow, floating ribbons and hair strands, ethereal dreamscape",
        "gently holding a glowing star lantern, lightly lifting dress hem with one hand while turning along a petal-strewn path",
        "leaning against a rustic balcony railing at dusk, breeze gently parting hair, thoughtful melancholic yet warm gaze toward horizon",
        "walking slowly barefoot along the water's edge, dress gently skimming reflective shallow water, glowing ripples expanding outward",
        "holding hands close to heart with fingers intertwined, eyes gently closed in quiet wish or prayer, serene glowing particles",
        "peeking around a doorway or flowering tree trunk with a playful curious expression, whimsical candid framing"
    ]
}

CAMERA_PERSPECTIVES = [
    "cinematic low angle perspective with dynamic diagonal framing and sense of scale",
    "slight high angle looking down with dramatic depth of field and soft circular bokeh",
    "dutch angle dynamic composition with foreground light elements",
    "cinematic wide three-quarter view with foreground light leaks and rim light",
    "intimate close-up portrait with shallow depth of field and glowing eye reflections",
    "wide environmental shot balancing the character silhouette with breathtaking panoramic scenery"
]

ATMOSPHERIC_SCENES = {
    "cosmic_fantasy": [
        "surrounded by glowing bioluminescent fireflies and floating golden light orbs under a starry cosmic night sky and nebula aurora",
        "magical dreamscape with floating clockwork gears, translucent pastel bubbles, and celestial starlight reflections",
        "vast crystal palace ruins floating among shattered asteroids, iridescent auroral curtains shimmering in space",
        "enchanted field of luminescent blue and white spider lilies blooming under a gigantic luminous crescent moon"
    ],
    "anime_daily": [
        "golden hour sunset on a high scenic rooftop with soft warm backlight, city skyline glowing in distant haze and fluffy cumulonimbus clouds",
        "tranquil cherry blossom stone staircase under dappled sunlight, pastel pink petals dancing gracefully in the spring breeze",
        "quaint retro sunlit cafe patio with trailing ivy, morning light filtering through wooden pergolas and casting delicate patterns",
        "seaside train station platform under clear azure summer sky, ocean waves glistening in distance with fresh coastal breeze"
    ],
    "cyber_festival": [
        "vibrant neon-lit festival night with floating paper lanterns, glowing bokeh lights, and romantic evening breeze",
        "futuristic cyberpunk street bathed in magenta and cyan neon glow, reflections shimmering in rain-slicked asphalt puddles",
        "bustling festival night market with stalls and hanging festival banners, golden sparks drifting from distant fireworks"
    ]
}

def enrich_prompt_with_dynamics(clean_prompt: str) -> str:
    p_lower = clean_prompt.lower()

    pose_keywords = ["坐", "躺", "跑", "战", "飞", "吃", "拿", "看", "笑", "站", "握", "跃", "挥", "pose", "stand", "sit", "run", "jump", "eating", "fighting"]
    scene_keywords = ["在", "背景", "天台", "海", "夜", "星", "森林", "花", "街", "房", "学", "城", "水", "空", "background", "scene", "night", "sky", "room"]
    multi_person_keywords = ["亲吻", "吻", "拥抱", "抱", "贴贴", "和", "与", "俩", "两人", "双人", "两只", "kiss", "hug", "together", "each other", "two girls", "couple", "yuri", "yaoi"]

    has_custom_pose = any(w in p_lower for w in pose_keywords)
    has_custom_scene = any(w in p_lower for w in scene_keywords)
    is_multi_person = any(w in p_lower for w in multi_person_keywords)

    modifiers = []

    # 1. 多人互动解剖防崩结构注入
    if is_multi_person:
        modifiers.append(MULTI_PERSON_ANATOMY_ANCHORS)

    # 2. 姿势补充
    if not has_custom_pose:
        has_action = any(w in p_lower for w in ["战", "打", "剑", "刀", "魔", "机甲", "fight", "battle", "sword", "weapon", "action"])
        has_dreamy = any(w in p_lower for w in ["星", "梦", "海", "空", "月", "花", "dream", "star", "space", "moon", "flower"])
        
        if has_action:
            chosen_pose = random.choice(THEMATIC_POSES["dynamic_action"])
        elif has_dreamy:
            chosen_pose = random.choice(THEMATIC_POSES["dreamy_poetic"])
        else:
            chosen_pose = random.choice(THEMATIC_POSES["cute_casual"])
        modifiers.append(chosen_pose)

    # 3. 镜头视角补充
    modifiers.append(random.choice(CAMERA_PERSPECTIVES))

    # 4. 场景氛围补充
    if not has_custom_scene:
        all_scenes = sum(ATMOSPHERIC_SCENES.values(), [])
        modifiers.append(random.choice(all_scenes))

    extra_str = ", ".join(modifiers)
    return f"{clean_prompt}. Dynamic artistic composition: {extra_str}"

async def _fetch_single_candidate(user_parts, variation_tag: str, timeout: float = 95.0) -> Optional[str]:
    """单路异步生图生成"""
    parts = list(user_parts) if isinstance(user_parts, list) else user_parts
    if isinstance(parts, list) and parts and parts[0].get("type") == "text":
        parts = [
            {"type": "text", "text": parts[0]["text"] + f"\nCamera & Composition Variation: {variation_tag}"}
        ] + parts[1:]
    elif isinstance(parts, str):
        parts = parts + f"\nCamera & Composition Variation: {variation_tag}"

    url = f"{BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    payload = {
        "model": IMAGE_GEN_MODEL,
        "messages": [{"role": "user", "content": parts}],
        "temperature": 0.95
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    m = re.search(r"data:image/(?:jpeg|png|webp|jpg);base64,([A-Za-z0-9+/=]+)", content)
                    if m:
                        return m.group(1)
                    m_url = re.search(r"https?://[^\s\)\"\']+\.(?:png|jpg|jpeg|webp)", content)
                    if m_url:
                        from .image import fetch_image_as_base64
                        b64_from_url = await fetch_image_as_base64(m_url.group(0))
                        if b64_from_url:
                            return re.sub(r"^data:image/[^;]+;base64,", "", b64_from_url)
    except Exception as e:
        print(f"[-] 候选图生成异常 ({variation_tag}): {e}")
    return None

async def generate_picture_gemini(
    prompt: str,
    reference_image_url: Optional[str] = None,
    candidate_count: int = IMAGE_GEN_CANDIDATES,
    timeout: float = 95.0
) -> Tuple[List[str], str]:
    """
    调用 gemini-3.1-flash-image 并发生成多张候选图像 (默认 2 张)，供视觉反思比选
    支持参考图生图 (Image-to-Image) 与多人互动解剖防崩结构锚点
    受到 1 分钟 8 张的滑动窗口频率保护
    返回: (candidate_base64_images_list, error_message)
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        return [], "绘画提示词为空喵。"

    # 1. 频率限制检查 (按候选张数扣除额度)
    allowed, reason = image_limiter.allow(count=candidate_count)
    if not allowed:
        return [], f"[绘图限频保护] {reason}"

    # 2. 动态姿势、多人解剖结构与场景丰富化
    enriched_prompt = enrich_prompt_with_dynamics(clean_prompt)

    # 3. 组装多模态提示词与参考图
    quality_booster = (
        "masterpiece, best quality, top tier anime visual, expressive character acting, "
        "anatomically correct limbs and hands with exactly five fingers per hand, "
        "flowing hair and dynamic fabric physics, cinematic volumetric lighting with rim light and rich atmospheric background"
    )

    if reference_image_url and reference_image_url.strip().startswith("http"):
        ref_u = reference_image_url.strip()
        print(f"[*] 启用参考图多模态生图 (严格隔离背景，用户指定场景优先): {ref_u[:60]}...")
        user_parts = [
            {
                "type": "text",
                "text": (
                    f"USER'S MANDATORY CORE INSTRUCTION (HIGHEST PRIORITY): {clean_prompt}\n\n"
                    f"REFERENCE IMAGE GUIDANCE: Use the provided reference image EXCLUSIVELY to recognize the character's facial features, hair style/color, and specific character design. "
                    f"CRITICAL OVERRIDE: DO NOT COPY THE BACKGROUND, SCENE, OR SURROUNDING ENVIRONMENT FROM THE REFERENCE IMAGE! "
                    f"You MUST place the characters into the EXACT setting and action demanded by the user above (Setting & Action: {clean_prompt}). "
                    f"Composition & Dynamic Style: {quality_booster}. Additional details: {enriched_prompt}"
                )
            },
            {
                "type": "image_url",
                "image_url": {"url": ref_u}
            }
        ]
    else:
        user_parts = (
            f"USER'S MANDATORY CORE INSTRUCTION: {clean_prompt}\n\n"
            f"Draw a high quality anime masterpiece with dynamic pose and expressive lighting: "
            f"{quality_booster}. Detailed composition: {enriched_prompt}"
        )

    # 4. 并发生成多张不同视角的候选图 (Candidate Variations)
    print(f"[*] 正在并发请求生成 {candidate_count} 张候选画面以供视觉自检比选...")
    variations = [
        "Variation A: Dynamic three-quarter cinematic view with atmospheric rim light",
        "Variation B: Intimate side profile view with shallow depth of field and soft romantic bokeh"
    ]

    tasks = [
        _fetch_single_candidate(user_parts, variations[i % len(variations)], timeout)
        for i in range(candidate_count)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid_candidates = [r for r in results if isinstance(r, str) and len(r) > 100]

    if valid_candidates:
        print(f"[+] 成功获取 {len(valid_candidates)} 张有效候选图！")
        return valid_candidates, ""

    return [], "未能生成有效候选图像，上游服务暂时未响应图像数据。"
