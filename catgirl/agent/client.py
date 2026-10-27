# -*- coding: utf-8 -*-
"""
异步 OpenAI 兼容客户端单例
使用 AsyncOpenAI 避免阻塞 asyncio 事件循环
"""

import httpx
from openai import AsyncOpenAI
from ..config import API_KEY, BASE_URL, LLM_TIMEOUT, LLM_MAX_RETRIES

_client: AsyncOpenAI = None

def get_llm_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=API_KEY,
            base_url=BASE_URL,
            timeout=httpx.Timeout(connect=15.0, read=LLM_TIMEOUT, write=20.0, pool=30.0),
            max_retries=LLM_MAX_RETRIES
        )
    return _client
