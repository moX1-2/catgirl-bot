# -*- coding: utf-8 -*-
"""
Gemini 3.1 Flash Image AI 绘图生成模块
支持利用 gemini-3.1-flash-image 绘制复杂高质量插画、二次元、写实场景与艺术图
内置 1 分钟 3 张的滑动窗口频率保护、随机动态姿势库与场景氛围增强 (彻底消除单调站桩)
"""

import re
import json
import random
import asyncio
from typing import Tuple, Optional
import httpx

from ..config import API_KEY, BASE_URL, IMAGE_GEN_MODEL
from ..limiter import image_limiter

# 动态姿势库 (当未指定具体姿势时智能随机抽选，赋予角色生命力与故事感)
DYNAMIC_POSES = [
    "leaning forward slightly with one hand reaching out toward viewer with open palm, gentle head tilt, dynamic foreshortening, intimate connection",
    "turning back to look over shoulder with a radiant cheerful smile, mid-motion running turn, hair and skirt fluttering dynamically in the wind",
    "floating weightlessly in mid-air in zero gravity, legs slightly curved, floating ribbons and hair strands, dreamy ethereal composition",
    "sitting comfortably on a scenic stone ledge or balustrade, dangling legs with one knee raised, relaxed natural posture, tilting head upward to the sky",
    "playful cute gesture with one hand making a soft cat paw or gentle peace sign near cheek, slight playful wink, expressive radiant face",
    "dynamic combat action stance with glowing energy particles swirling around hands, dramatic low angle shot, hair billowing with motion blur",
    "holding a delicious sweet treat or drink with both hands, taking a tiny cute bite with softly blushing cheeks, charming candid moment",
    "gently holding a parasol or glowing star lantern, lightly lifting dress hem with one hand while turning, petal-strewn breeze",
    "resting chin in hand while gazing thoughtfully into the distance, soft breeze parting hair, cinematic depth of field"
]

# 镜头构图与透视视角库
CAMERA_PERSPECTIVES = [
    "cinematic low angle perspective with dynamic diagonal framing",
    "slight high angle looking down with dramatic depth of field and soft bokeh",
    "dutch angle dynamic composition with foreground light elements",
    "cinematic wide three-quarter view with foreground bokeh and rim light",
    "intimate close-up portrait with cinematic depth of field and glowing eye reflections"
]

# 电影级场景氛围库 (当未指定背景时智能随机融入)
ATMOSPHERIC_SCENES = [
    "surrounded by glowing bioluminescent fireflies and floating golden light orbs under a starry cosmic night sky",
    "golden hour sunset on a high scenic rooftop with soft warm backlight, city skyline glowing in distant haze",
    "magical dreamscape with floating clockwork gears, translucent pastel bubbles, and starlight reflections",
    "lush flowering garden under dappled sunlight, blooming cherry blossom petals dancing in the air",
    "vibrant neon-lit festival night with bokeh lanterns and romantic evening breeze",
    "serene lakeside at dawn, morning mist rising with glowing water reflections and floating crystal fragments"
]

def enrich_prompt_with_dynamics(clean_prompt: str) -> str:
    """
    根据用户输入智能判断：
    - 若用户已明确指定动作或场景，严格保留并仅补充镜头与光影；
    - 若输入较为简单（如仅角色名），自动融入生动的动态姿势与电影级场景氛围，彻底拒绝死板证件照！
    """
    pose_keywords = ["坐", "躺", "跑", "战", "飞", "吃", "拿", "看", "笑", "站", "握", "跃", "挥", "pose", "stand", "sit", "run", "jump", "eating", "fighting"]
    scene_keywords = ["在", "背景", "天台", "海", "夜", "星", "森林", "花", "街", "房", "学", "城", "水", "空", "background", "scene", "night", "sky", "room"]

    has_custom_pose = any(w in clean_prompt for w in pose_keywords)
    has_custom_scene = any(w in clean_prompt for w in scene_keywords)

    modifiers = []
    if not has_custom_pose:
        modifiers.append(random.choice(DYNAMIC_POSES))
    modifiers.append(random.choice(CAMERA_PERSPECTIVES))
    if not has_custom_scene:
        modifiers.append(random.choice(ATMOSPHERIC_SCENES))

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
