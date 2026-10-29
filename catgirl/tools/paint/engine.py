# -*- coding: utf-8 -*-
"""
生图调用引擎与双候选并发调度器 (Paint Engine)
"""

import re
import asyncio
from typing import Tuple, List, Optional
import httpx

from ...config import API_KEY, BASE_URL, IMAGE_GEN_MODEL, IMAGE_GEN_CANDIDATES
from ...limiter import image_limiter
from .composer import compose_generation_payload

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
                        from ..image import fetch_image_as_base64
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
    模块化装配与并发双候选调用主入口
    受到 1 分钟 8 张滑动窗口保护
    返回: (candidate_base64_images_list, error_message)
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        return [], "绘画提示词为空喵。"

    # 1. 频率限制检查 (按候选张数扣除额度)
    allowed, reason = image_limiter.allow(count=candidate_count)
    if not allowed:
        return [], f"[绘图限频保护] {reason}"

    # 2. 模块化动态上下文装配 Payload
    user_payload = compose_generation_payload(clean_prompt, reference_image_url)

    # 3. 并发双候选生成
    print(f"[*] 模块化生图引擎启动: 并发生成 {candidate_count} 张候选画面以供比选...")
    variations = [
        "Variation A: Dynamic three-quarter cinematic view with atmospheric rim light",
        "Variation B: Intimate side profile view with shallow depth of field and soft romantic bokeh"
    ]

    tasks = [
        _fetch_single_candidate(user_payload, variations[i % len(variations)], timeout)
        for i in range(candidate_count)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid_candidates = [r for r in results if isinstance(r, str) and len(r) > 100]

    if valid_candidates:
        print(f"[+] 模块化生图成功获取 {len(valid_candidates)} 张有效候选图！")
        return valid_candidates, ""

    return [], "未能生成有效候选图像，上游服务暂时未响应图像数据。"
