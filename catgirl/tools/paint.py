# -*- coding: utf-8 -*-
"""
Gemini 3.1 Flash Image AI 绘图生成模块
支持利用 gemini-3.1-flash-image 绘制高质量插画、二次元、写实场景与艺术图
内置 1 分钟 3 张滑动窗口保护、多主题分类动态姿势与电影级构图场景扩充库
"""

import re
import json
import random
import asyncio
from typing import Tuple, Optional
import httpx

from ..config import API_KEY, BASE_URL, IMAGE_GEN_MODEL
from ..limiter import image_limiter

# ================== 多维度生动姿势分类库 (Danbooru & Illustrious 级动作提炼) ==================
THEMATIC_POSES = {
    # 1. 软萌日常与亲昵互动 (Cute & Casual)
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
    # 2. 高燃战斗与疾走动感 (Dynamic & Action)
    "dynamic_action": [
        "dynamic combat action stance with glowing energy particles swirling around hands, dramatic low angle shot, hair billowing with motion blur",
        "turning back mid-motion to look over shoulder with a radiant determined expression, running turn, dynamic hair and skirt fluttering in the wind",
        "drawing sword from scabbard with crisp diagonal motion, blade catching a brilliant gleam of light, sharp focused gaze",
        "mid-air acrobatic leap, one leg extended and ribbons spiraling outward, dynamic diagonal camera framing",
        "landing from a jump with one hand touching the ground, shockwave energy ripples expanding beneath feet, dramatic foreshortening",
        "casting an intricate glowing magic circle in front of hands, concentrated magic glow illuminating face in sharp contrast",
        "holding weapons ready at side, turning sharply with motion blur, fierce intense eyes, dynamic perspective"
    ],
    # 3. 唯美意境与轻盈空灵 (Dreamy & Ethereal)
    "dreamy_poetic": [
        "floating weightlessly in mid-air in zero gravity, legs slightly curved in elegant flow, floating ribbons and hair strands, ethereal dreamscape",
        "gently holding a glowing star lantern, lightly lifting dress hem with one hand while turning along a petal-strewn path",
        "leaning against a rustic balcony railing at dusk, breeze gently parting hair, thoughtful melancholic yet warm gaze toward horizon",
        "walking slowly barefoot along the water's edge, dress gently skimming reflective shallow water, glowing ripples expanding outward",
        "holding hands close to heart with fingers intertwined, eyes gently closed in quiet wish or prayer, serene glowing particles",
        "peeking around a doorway or flowering tree trunk with a playful curious expression, whimsical candid framing"
    ]
}

# 镜头构图与透视视角库
CAMERA_PERSPECTIVES = [
    "cinematic low angle perspective with dynamic diagonal framing and sense of scale",
    "slight high angle looking down with dramatic depth of field and soft circular bokeh",
    "dutch angle dynamic composition with foreground light elements",
    "cinematic wide three-quarter view with foreground light leaks and rim light",
    "intimate close-up portrait with shallow depth of field and glowing eye reflections",
    "wide environmental shot balancing the character silhouette with breathtaking panoramic scenery"
]

# 电影级场景氛围库
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
    """
    根据用户输入智能判断：
    - 若用户已明确指定动作或场景，严格保留并仅补充镜头视角与光影；
    - 若未具体指定动作，按语义智能匹配（战斗/软萌/唯美/日常）抽选生动的姿势与镜头！
    """
    p_lower = clean_prompt.lower()

    pose_keywords = ["坐", "躺", "跑", "战", "飞", "吃", "拿", "看", "笑", "站", "握", "跃", "挥", "pose", "stand", "sit", "run", "jump", "eating", "fighting"]
    scene_keywords = ["在", "背景", "天台", "海", "夜", "星", "森林", "花", "街", "房", "学", "城", "水", "空", "background", "scene", "night", "sky", "room"]

    has_custom_pose = any(w in p_lower for w in pose_keywords)
    has_custom_scene = any(w in p_lower for w in scene_keywords)

    modifiers = []

    # 1. 姿势补充
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

    # 2. 镜头视角补充
    modifiers.append(random.choice(CAMERA_PERSPECTIVES))

    # 3. 场景氛围补充
    if not has_custom_scene:
        all_scenes = sum(ATMOSPHERIC_SCENES.values(), [])
        modifiers.append(random.choice(all_scenes))

    extra_str = ", ".join(modifiers)
    return f"{clean_prompt}. Dynamic artistic composition: {extra_str}"

async def generate_picture_gemini(
    prompt: str,
    reference_image_url: Optional[str] = None,
    timeout: float = 95.0
) -> Tuple[Optional[str], str]:
    """
    调用 gemini-3.1-flash-image 生成高质量图像 Base64
    全面支持文生图与【参考图生图 (Image-to-Image)】
    受到 1 分钟 3 次的滑动窗口频率限制
    自动注入动态姿势与戏剧性视角增强
    返回: (base64_image_data, error_message)
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        return None, "绘画提示词为空喵。"

    # 1. 频率限制检查 (1分钟3张)
    allowed, reason = image_limiter.allow()
    if not allowed:
        return None, f"[绘图限频保护] {reason}"

    # 2. 动态姿势与场景丰富化
    enriched_prompt = enrich_prompt_with_dynamics(clean_prompt)

    # 3. 组装多模态提示词与参考图
    quality_booster = (
        "masterpiece, best quality, top tier anime visual, expressive character acting, "
        "flowing hair and dynamic fabric physics, cinematic volumetric lighting with rim light and rich atmospheric background"
    )

    if reference_image_url and reference_image_url.strip().startswith("http"):
        ref_u = reference_image_url.strip()
        print(f"[*] 启用参考图多模态生图 (带动态姿势强化): {ref_u[:60]}...")
        user_parts = [
            {
                "type": "text",
                "text": (
                    f"Faithfully preserve the character identity, outfit, face, and colors from the provided reference image, "
                    f"but render them in a lively, exciting, non-monotonous anime pose with expressive interaction and cinematic atmosphere: "
                    f"{quality_booster}. Description: {enriched_prompt}"
                )
            },
            {
                "type": "image_url",
                "image_url": {"url": ref_u}
            }
        ]
    else:
        user_parts = (
            f"Draw a high quality anime masterpiece with dynamic pose and expressive lighting: "
            f"{quality_booster}. Description: {enriched_prompt}"
        )

    url = f"{BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    payload = {
        "model": IMAGE_GEN_MODEL,
        "messages": [
            {"role": "user", "content": user_parts}
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    # 匹配 base64 图像
                    m = re.search(r"data:image/(?:jpeg|png|webp|jpg);base64,([A-Za-z0-9+/=]+)", content)
                    if m:
                        b64_img = m.group(1)
                        return b64_img, ""
                    # 匹配普通 HTTP URL
                    m_url = re.search(r"https?://[^\s\)\"\']+\.(?:png|jpg|jpeg|webp)", content)
                    if m_url:
                        from .image import fetch_image_as_base64
                        b64_from_url = await fetch_image_as_base64(m_url.group(0))
                        if b64_from_url:
                            b64_clean = re.sub(r"^data:image/[^;]+;base64,", "", b64_from_url)
                            return b64_clean, ""
                return None, "绘图模型未输出有效图像数据。"
            else:
                return None, f"绘图模型返回状态码 {resp.status_code}: {resp.text[:120]}"
    except Exception as e:
        return None, f"绘图生成异常: {e}"
