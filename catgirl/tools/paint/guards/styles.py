# -*- coding: utf-8 -*-
"""
环境氛围与画质光影增强模块 (Styles & Atmosphere Guard)
"""

import random

ATMOSPHERIC_SCENES = [
    "surrounded by glowing bioluminescent fireflies and floating golden light orbs under a starry cosmic night sky and nebula aurora",
    "magical dreamscape with floating clockwork gears, translucent pastel bubbles, and celestial starlight reflections",
    "vast crystal palace ruins floating among shattered asteroids, iridescent auroral curtains shimmering in space",
    "golden hour sunset on a high scenic rooftop with soft warm backlight, city skyline glowing in distant haze and fluffy cumulonimbus clouds",
    "tranquil cherry blossom stone staircase under dappled sunlight, pastel pink petals dancing gracefully in the spring breeze",
    "quaint retro sunlit cafe patio with trailing ivy, morning light filtering through wooden pergolas and casting delicate patterns",
    "seaside train station platform under clear azure summer sky, ocean waves glistening in distance with fresh coastal breeze",
    "vibrant neon-lit festival night with floating paper lanterns, glowing bokeh lights, and romantic evening breeze",
    "sunny tropical beach with turquoise ocean waves crashing on white sand under radiant summer sun"
]

MASTERPIECE_BOOSTER = (
    "masterpiece, best quality, top tier anime visual, expressive character acting, "
    "flowing hair and dynamic fabric physics, cinematic volumetric lighting with rim light and rich atmospheric background"
)

CUSTOM_SCENE_KEYWORDS = [
    "在", "背景", "天台", "海", "夜", "星", "森林", "花", "街", "房", "学", "城", "水", "空", "沙滩",
    "background", "scene", "night", "sky", "room", "beach"
]

def pick_atmosphere(prompt: str) -> str:
    """若用户未指定背景场景，自动补充电影级意境氛围"""
    p_lower = prompt.lower()
    has_custom = any(kw in p_lower for kw in CUSTOM_SCENE_KEYWORDS)
    if not has_custom:
        return random.choice(ATMOSPHERIC_SCENES)
    return ""
