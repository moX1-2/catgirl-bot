# -*- coding: utf-8 -*-
"""
网页深度抓取与正文提取服务 (Web Page Extractor)
支持 Tavily Extract API 智能降噪提取与 httpx 降级抓取
"""

import re
import html
import asyncio
from typing import Optional
import httpx

from ..config import TAVILY_KEYS

async def fetch_web_page_content(url: str, max_chars: int = 4000, timeout: float = 15.0) -> str:
    """
    抓取指定网页的正文详细内容。
    优先使用 Tavily Extract API (多 Key 故障转移)，备选使用 httpx 纯文本降级抽取。
    """
    clean_url = html.unescape(url).strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        return "无效的 URL 网址，必须以 http:// 或 https:// 开头喵。"

    # 1. 优先尝试 Tavily Extract API (智能提取 LLM 优化 Markdown 正文)
    for idx, key in enumerate(TAVILY_KEYS):
        try:
            payload = {
                "api_key": key,
                "urls": [clean_url]
            }
            async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                resp = await client.post("https://api.tavily.com/extract", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        raw_c = results[0].get("raw_content", "") or ""
                        if raw_c.strip():
                            text_trimmed = raw_c.strip()
                            if len(text_trimmed) > max_chars:
                                text_trimmed = text_trimmed[:max_chars] + f"\n...[正文过长，已截取前 {max_chars} 字符]..."
                            return f"【网页抓取成功: {clean_url}】\n{text_trimmed}"
        except Exception as e:
            print(f"[-] Tavily Extract Key {idx+1} 抓取异常: {e}")
            continue

    # 2. 备选尝试 httpx 直接抓取与正则剥离
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=True) as client:
            resp = await client.get(clean_url, headers=headers)
            if resp.status_code == 200:
                html_text = resp.text
                # 剥离 script, style 标签
                clean_html = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", html_text, flags=re.I)
                clean_html = re.sub(r"<[^>]+>", " ", clean_html)
                clean_html = re.sub(r"\s+", " ", clean_html).strip()
                if len(clean_html) > max_chars:
                    clean_html = clean_html[:max_chars] + f"\n...[网页内容过长，已折叠]..."
                return f"【网页直接抓取成功: {clean_url}】\n{clean_html}"
            else:
                return f"抓取网页失败: 目标服务器返回状态码 {resp.status_code}喵。"
    except Exception as e:
        return f"抓取网页发生异常: {e}喵。"
