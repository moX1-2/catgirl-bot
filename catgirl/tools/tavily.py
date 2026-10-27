# -*- coding: utf-8 -*-
"""
Tavily 搜索网关
提供多 API Key 自动容错轮换与流量保护速率限制
"""

import re
import json
import urllib.request
import httpx
from ..config import TAVILY_KEYS
from ..limiter import search_limiter

async def perform_tavily_search(query: str, max_results: int = 4) -> str:
    """
    执行 Tavily 联网搜索。具备多 Key 故障转移机制与滑动窗口限流。
    """
    allowed, reason = search_limiter.allow()
    if not allowed:
        return f"[搜索限流保护] {reason}"
    clean_q = query.strip()
    clean_q = clean_q.replace('"', ' ').replace("'", ' ').strip()
    clean_q = re.sub(r'\s+', ' ', clean_q)
    if not clean_q:
        return "搜索关键词为空。"

    for idx, key in enumerate(TAVILY_KEYS):
        try:
            payload = {
                "api_key": key,
                "query": clean_q,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": True
            }
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                resp = await http_client.post("https://api.tavily.com/search", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data.get("answer", "")
                    results = data.get("results", [])
                    lines = [f"【联网搜索结果: {clean_q}】"]
                    if answer:
                        lines.append(f"智能摘要: {answer}")
                    for i, r in enumerate(results[:3], 1):
                        title = r.get("title", "网页")
                        url = r.get("url", "")
                        snippet = r.get("content", "")[:180].strip()
                        lines.append(f"[{i}] {title}\n    链接: {url}\n    摘要: {snippet}")
                    return "\n".join(lines)
                else:
                    print(f"[-] Tavily key {idx+1} 返回状态码 {resp.status_code}")
        except Exception as e:
            print(f"[-] Tavily key {idx+1} 搜索异常: {e}")
            continue

    return "抱歉，所有备用搜索密钥均未响应或网络暂时超时喵。"
