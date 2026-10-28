# -*- coding: utf-8 -*-
"""
Gemini 3.1 Flash Image AI 绘图生成模块
支持利用 gemini-3.1-flash-image 绘制复杂高质量插画、二次元、写实场景与艺术图
内置 1 分钟 1 张的严格频率保护
"""

import re
import json
import asyncio
from typing import Tuple, Optional
import httpx

from ..config import API_KEY, BASE_URL, IMAGE_GEN_MODEL
from ..limiter import image_limiter

async def generate_picture_gemini(
    prompt: str,
    reference_image_url: Optional[str] = None,
    timeout: float = 95.0
) -> Tuple[Optional[str], str]:
    """
    调用 gemini-3.1-flash-image 生成高质量图像 Base64
    全面支持文生图与【参考图生图 (Image-to-Image)】
    受到 1 分钟 1 次的严格频率限制
    返回: (base64_image_data, error_message)
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        return None, "绘画提示词为空喵。"

    # 1. 频率限制检查 (1分钟1张)
    allowed, reason = image_limiter.allow()
    if not allowed:
        return None, f"[绘图限频保护] {reason}"

    # 2. 组装多模态提示词与参考图
    if reference_image_url and reference_image_url.strip().startswith("http"):
        ref_u = reference_image_url.strip()
        print(f"[*] 启用参考图多模态绘图: {ref_u[:60]}...")
        user_parts = [
            {
                "type": "text",
                "text": f"Reference the character and object appearance, colors, and key visual features from the provided reference image to generate a high quality artwork: {clean_prompt}"
            },
            {
                "type": "image_url",
                "image_url": {"url": ref_u}
            }
        ]
    else:
        user_parts = f"Draw a high quality masterpiece image: {clean_prompt}"

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
