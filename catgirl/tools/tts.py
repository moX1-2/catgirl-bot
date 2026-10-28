# -*- coding: utf-8 -*-
"""
Gemini 3.8 Flash TTS 语音合成服务
采用官方推荐的 Director 导演提示词与 Despina 轻快二次元声线
具备自然连贯的韵律流与多模型自动故障转移池
"""

import json
import asyncio
from typing import Tuple, Optional
import httpx

from ..config import GEMINI_TTS_KEY

# Gemini 官方默认端点与模型故障转移池
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TTS_MODEL_CANDIDATES = [
    "gemini-3.8-flash-lite-tts",
    "gemini-3.1-flash-tts-preview",
    "gemini-3.8-flash-tts"
]

# 经实测验证的最佳猫娘导演提示词 (确保中文连贯、语调轻快自然、杜绝机械断句)
CATGIRL_DIRECTOR_PROMPT = (
    "Voice Style: A playful, sweet, young anime catgirl character. "
    "Speak in natural and fluent Mandarin Chinese with smooth, connected phrasing, "
    "joyful cadence, conversational inflection, and emotional liveliness without unnatural pauses."
)

async def generate_speech_gemini(
    text: str,
    voice_name: str = "Despina",
    timeout: float = 25.0
) -> Tuple[Optional[str], str]:
    """
    调用 Gemini 3.8 Flash TTS 将文本转换为自然连贯的二次元猫娘语音
    返回: (base64_audio_data, error_message)
    """
    clean_text = text.strip()
    if not clean_text:
        return None, "待合成语音文本为空。"

    if not GEMINI_TTS_KEY:
        return None, "未配置 GEMINI_TTS_KEY，无法使用语音功能喵。"

    # 口语微调：去除过硬标点，保持连贯猫娘语感
    if not clean_text.endswith(("喵", "喵~", "喵！", "！", "？", "~", "呢")):
        clean_text += "喵~"

    # 注入 Director 导演提示词
    full_prompt = f"{CATGIRL_DIRECTOR_PROMPT}\n\n{clean_text}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": full_prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice_name
                    }
                }
            }
        }
    }

    last_err = ""
    for model_name in TTS_MODEL_CANDIDATES:
        url = f"{GEMINI_API_BASE}/{model_name}:generateContent?key={GEMINI_TTS_KEY}"
        try:
            async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for p in parts:
                            inline_data = p.get("inlineData")
                            if inline_data and inline_data.get("data"):
                                raw_b64 = inline_data["data"]
                                return raw_b64, ""
                elif resp.status_code == 429:
                    print(f"[-] Gemini TTS 模型 {model_name} 配额繁忙，切换备选模型...")
                    last_err = f"模型 {model_name} 429 忙"
                    continue
                else:
                    last_err = f"模型 {model_name} 状态码 {resp.status_code}"
                    continue
        except Exception as e:
            print(f"[-] Gemini TTS 请求异常 ({model_name}): {e}")
            last_err = str(e)
            continue

    return None, f"语音合成失败: {last_err}"
