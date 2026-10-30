# -*- coding: utf-8 -*-
"""
海螺 AI (MiniMax) T2A v2 旗舰级语音合成服务
专为二次元猫娘设计的甜美拟真人声引擎 (彻底解决 Gemini TTS 一天仅 10 条的配额瓶颈)
"""

import json
import base64
import asyncio
from typing import Tuple, Optional
import httpx

from ..config import (
    MINIMAX_API_KEY,
    MINIMAX_GROUP_ID,
    MINIMAX_VOICE_ID,
    MINIMAX_PITCH,
    MINIMAX_SPEED,
    MINIMAX_EMOTION
)

# MiniMax T2A v2 官方标准接口
MINIMAX_API_URL = "https://api.minimax.chat/v1/t2a_v2"

# 推荐音色表
VOICE_PRESETS = {
    "tianmei": "female-tianmei",  # 招牌甜美少女/猫娘音 (推荐)
    "shaonv": "female-shaonv",    # 元气活泼少女音
    "yujie": "female-yujie",      # 温柔治愈御姐音
    "boy": "cute_boy"             # 活力正太音
}

async def generate_speech_minimax(
    text: str,
    voice_name: str = None,
    timeout: float = 25.0
) -> Tuple[Optional[str], str]:
    """
    调用海螺 AI (MiniMax) T2A v2 接口将文本转换为高保真拟真人声
    返回: (base64_audio_data, error_message)
    """
    clean_text = text.strip()
    if not clean_text:
        return None, "待合成语音文本为空喵。"

    if not MINIMAX_API_KEY:
        return None, "未配置 MINIMAX_API_KEY 喵！请主人在 .env 中填入海螺 AI 的 API Key 与 Group ID 开启专属语音喵~"

    # 音色选择 (默认选用甜美少女音)
    target_voice = MINIMAX_VOICE_ID or "female-tianmei"
    if voice_name and voice_name.lower() in VOICE_PRESETS:
        target_voice = VOICE_PRESETS[voice_name.lower()]
    elif voice_name:
        target_voice = voice_name

    # 规范口语猫娘尾音
    if not clean_text.endswith(("喵", "喵~", "喵！", "！", "？", "~", "呢")):
        clean_text += "喵~"

    # 拼接 GroupId URL
    url = f"{MINIMAX_API_URL}?GroupId={MINIMAX_GROUP_ID}" if MINIMAX_GROUP_ID else MINIMAX_API_URL

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }

    # 智能台词剧本优化：替换生硬标点，注入自然呼吸与换气律动
    script_text = clean_text
    script_text = script_text.replace("...", "……").replace("！", "！ ").replace("~", "~ ")

    payload = {
        "model": "speech-01-turbo",
        "text": script_text,
        "stream": False,
        "voice_setting": {
            "voice_id": target_voice,
            "speed": MINIMAX_SPEED,      # 1.08x (试听方案B锁定：轻快灵动不拖沓)
            "vol": 1.0,
            "pitch": MINIMAX_PITCH,      # +2 半音 (试听方案B锁定：娇俏元气猫娘声线)
            "emotion": MINIMAX_EMOTION   # happy (欢快情绪起伏)
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1
        }
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                res_data = resp.json()
                base_resp = res_data.get("base_resp", {})
                status_code = base_resp.get("status_code")
                if status_code == 0:
                    hex_audio = res_data.get("data", {}).get("audio", "")
                    if hex_audio:
                        raw_bytes = bytes.fromhex(hex_audio)
                        b64_audio = base64.b64encode(raw_bytes).decode("utf-8")
                        return b64_audio, ""
                    return None, "海螺返回的音频流为空。"
                else:
                    msg = base_resp.get("status_msg", "未知错误")
                    print(f"[-] 海螺 TTS 业务报错 ({status_code}): {msg}")
                    return None, f"海螺 TTS 错误: {msg}"
            else:
                return None, f"海螺 HTTP 状态码 {resp.status_code}: {resp.text[:120]}"
    except Exception as e:
        print(f"[-] 海螺 TTS 网络请求异常: {e}")
        return None, f"海螺 TTS 请求异常: {e}"

# 统一别名
generate_speech = generate_speech_minimax

# 向后兼容别名
generate_speech_gemini = generate_speech_minimax
