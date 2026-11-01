# -*- coding: utf-8 -*-
"""
B站视频多模态逐秒视觉深度解析模块
利用移动端与开放流媒体接口获取轻量视频流，结合 ffmpeg 抽帧瘦身管线 (1fps / 360p)，
通过 Google Generative Language 原生协议将视频直传给 gemini-3.8-flash-medium，
输出包含精确时间轴、画面分镜细节与猫娘观后感的深度长文解析。
解析完毕后立即清理本地临时视频切片，保持 2C2G 服务器轻量与稳定。
"""

import os
import re
import time
import json
import base64
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import requests

from ..config import (
    API_KEY,
    BASE_URL,
    MODEL_NAME
)

CACHE_DIR = Path("/tmp/catgirl_video_cache")
_video_lock = asyncio.Lock()


def _ensure_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def extract_bvid_from_url(text: str) -> Optional[str]:
    """从文本中提取 BV号 或 处理 b23.tv 短链"""
    if not text:
        return None
    raw = text.strip()

    # 直接匹配 BV 号
    m_bv = re.search(r"(BV[0-9a-zA-Z]{10})", raw)
    if m_bv:
        return m_bv.group(1)

    # 匹配 b23.tv 短链并自动跟随重定向
    m_short = re.search(r"https?://(?:b23.tv|bili2233.cn)/([a-zA-Z0-9]+)", raw)
    if m_short:
        short_url = m_short.group(0)
        try:
            r = requests.head(short_url, allow_redirects=True, timeout=5)
            m_target = re.search(r"(BV[0-9a-zA-Z]{10})", r.url)
            if m_target:
                return m_target.group(1)
        except Exception as e:
            print(f"[-] 解析 b23 短链重定向失败: {e}")

    # 匹配传统 av 号并自动转换
    m_av = re.search(r"av(\d+)", raw, re.I)
    if m_av:
        aid = m_av.group(1)
        try:
            view_url = os.getenv("BILIBILI_VIEW_URL", "https://api.bilibili.com/x/web-interface/view")
            r_av = requests.get(f"{view_url}?aid={aid}", timeout=5).json()
            if r_av.get("code") == 0 and r_av.get("data", {}).get("bvid"):
                return r_av["data"]["bvid"]
        except Exception:
            pass

    return None


def _get_bilibili_cookies_and_headers() -> Tuple[Dict[str, str], Dict[str, str]]:
    """获取公开游客指纹 Cookie 与标准防盗链请求头"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com"
    }
    cookies = {}
    spi_url = os.getenv("BILIBILI_SPI_URL", "https://api.bilibili.com/x/frontend/finger/spi")
    try:
        r = requests.get(spi_url, headers=headers, timeout=5).json()
        b_3 = r.get("data", {}).get("b_3", "")
        b_4 = r.get("data", {}).get("b_4", "")
        if b_3:
            cookies["buvid3"] = f"{b_3}infoc"
        if b_4:
            cookies["buvid4"] = b_4
    except Exception as e:
        print(f"[-] 获取 B站 指纹失败: {e}")

    return headers, cookies


def _fetch_video_info_and_stream(bvid: str) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """获取视频元数据并提取低清晰度 (360P) 视频流下载直链"""
    headers, cookies = _get_bilibili_cookies_and_headers()
    view_url = os.getenv("BILIBILI_VIEW_URL", "https://api.bilibili.com/x/web-interface/view")

    try:
        r_v = requests.get(f"{view_url}?bvid={bvid}", headers=headers, cookies=cookies, timeout=8).json()
        if r_v.get("code") != 0:
            return None, None, f"视频不存在或受访问限制: {r_v.get('message')}"

        v_data = r_v.get("data", {})
        title = v_data.get("title", "")
        owner_name = v_data.get("owner", {}).get("name", "")
        cid = v_data.get("cid")
        duration = v_data.get("duration", 0)
        desc = v_data.get("desc", "")

        meta = {
            "bvid": bvid,
            "title": title,
            "owner": owner_name,
            "duration": duration,
            "desc": desc
        }

        # 获取播放直链 (使用 qn=16 即 360P 流，体积超小、下载秒级完成)
        play_api = os.getenv("BILIBILI_PLAYURL", "https://api.bilibili.com/x/player/playurl")
        pu_url = f"{play_api}?bvid={bvid}&cid={cid}&qn=16&type=mp4&platform=html5"
        r_p = requests.get(pu_url, headers=headers, cookies=cookies, timeout=8).json()
        if r_p.get("code") != 0:
            return None, meta, f"获取视频流地址失败: {r_p.get('message')}"

        durls = r_p.get("data", {}).get("durl", [])
        if not durls:
            return None, meta, "该视频未返回可用的流媒体直链 (可能为大会员专享或互动视频)"

        stream_url = durls[0].get("url")
        return stream_url, meta, None

    except Exception as e:
        return None, None, f"请求 B站 接口异常: {e}"


def _download_and_slim_video(stream_url: str, bvid: str, duration: int) -> Tuple[Optional[str], Optional[str]]:
    """流式下载并使用 ffmpeg 1fps 极限瘦身"""
    cache_dir = _ensure_cache_dir()
    raw_path = cache_dir / f"{bvid}_raw.mp4"
    slim_path = cache_dir / f"{bvid}_slim.mp4"

    headers, _ = _get_bilibili_cookies_and_headers()

    try:
        # 1. 流式下载 (若视频较长，限制下载大小避免耗尽磁盘)
        print(f"[*] 正在流式下载 B站视频流 (时长: {duration}秒)...")
        resp = requests.get(stream_url, headers=headers, stream=True, timeout=20)
        total_downloaded = 0
        max_bytes = 25 * 1024 * 1024  # 上限 25MB

        with open(raw_path, "wb") as f_raw:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    break
                f_raw.write(chunk)
                total_downloaded += len(chunk)
                if total_downloaded >= max_bytes:
                    print(f"[*] 已达到防爆上限 {max_bytes//(1024*1024)}MB，提前截断")
                    break

        # 2. ffmpeg 1fps 抽帧瘦身 (Gemini 视觉底座采样率正好为 1fps，完美契合且无损视觉理解)
        print(f"[*] 正在执行 ffmpeg 极速瘦身抽帧 (1fps, 360p, crf=32)...")
        cmd = [
            "ffmpeg", "-y", "-i", str(raw_path),
            "-vf", "scale=480:-2,fps=1",
            "-c:v", "libx264", "-crf", "32", "-preset", "veryfast", "-an",
            str(slim_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=40)
        if res.returncode == 0 and slim_path.exists() and slim_path.stat().st_size > 5000:
            print(f"[+] 视频瘦身就绪: {slim_path.stat().st_size} bytes (原视频: {total_downloaded} bytes)")
            return str(slim_path), None
        else:
            return None, "ffmpeg 视频抽帧压缩处理失败"

    except Exception as e:
        return None, f"视频下载或压制失败: {e}"
    finally:
        if raw_path.exists():
            try:
                raw_path.unlink(missing_ok=True)
            except Exception:
                pass


async def analyze_bilibili_video(url: str, focus_prompt: Optional[str] = None) -> str:
    """
    B站视频视觉深度解析主函数：
    1. 提取 BV号
    2. 获取轻量视频流并执行 1fps 瘦身
    3. 携带多模态 Base64 视频直传给 gemini-3.8-flash-medium 视觉模型
    4. 释放本地视频缓存
    5. 返回带精准时间轴、画面细节、名梗与猫娘观后感的长文
    """
    bvid = extract_bvid_from_url(url)
    if not bvid:
        return f"未能从你提供的链接中识别到有效的 B站 BV号 或短链喵，请检查链接是否正确~"

    async with _video_lock:
        print(f"[*] 开始解析 B站视频: {bvid}")
        loop = asyncio.get_running_loop()

        # 1. 抓取元数据与直链
        stream_url, meta, err = await loop.run_in_executor(None, _fetch_video_info_and_stream, bvid)
        if not stream_url or err:
            return f"喵呜~ 解析 B站视频失败: {err}"

        # 2. 下载并抽帧瘦身
        duration = meta.get("duration", 0)
        slim_path, err_dl = await loop.run_in_executor(None, _download_and_slim_video, stream_url, bvid, duration)
        if not slim_path or err_dl:
            return f"喵呜~ 视频流抓取或压缩失败: {err_dl}"

        # 3. 读取 Base64 视频并提交给 Gemini 3.8 Flash Medium
        try:
            with open(slim_path, "rb") as f_slim:
                b64_video = base64.b64encode(f_slim.read()).decode("utf-8")

            # 清洗 base_url 提取 Google 原生端点
            clean_base = BASE_URL.rstrip("/")
            if clean_base.endswith("/v1"):
                clean_base = clean_base[:-3]
            api_endpoint = f"{clean_base}/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"

            prompt_text = (
                f"你现在作为元气、聪颖且观察敏锐的猫娘「阿橘」，请仔细观看这段完整B站视频（UP主: {meta['owner']}，标题: 《{meta['title']}》）。\n"
                "请结合视觉画面、每一秒的动态变化、画面文字/弹幕、剧情走向与细节，输出一份深度详实、排版清爽专业的观后感长文喵！\n"
                "必须包含以下结构：\n"
                "1. 【全片时间轴与关键分镜】（以 00:00 分秒标注时间点，指出每一段发生了什么、画面呈现了什么关键场景/道具/动作/文字）；\n"
                "2. 【核心亮点与视觉细节】（指出画面背景中的隐藏彩蛋、弹幕名梗、表情包或反转细节）；\n"
                "3. 【阿橘深度观后感】（以生动、有见地且带有猫猫口吻的语气点评全片精彩之处与思考）。\n"
            )
            if focus_prompt:
                prompt_text += f"\n【用户特别叮嘱的分析重点】: {focus_prompt}\n"

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt_text},
                            {
                                "inline_data": {
                                    "mime_type": "video/mp4",
                                    "data": b64_video
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.8,
                    "maxOutputTokens": 2048
                }
            }

            print(f"[*] 正在将瘦身后的视频 ({len(b64_video)} Base64字符) 提交给 {MODEL_NAME} 深度审阅...")
            headers = {"Content-Type": "application/json"}
            
            def _call_gemini():
                return requests.post(api_endpoint, json=payload, headers=headers, timeout=80)

            r_gen = await loop.run_in_executor(None, _call_gemini)
            if r_gen.status_code != 200:
                return f"视频视觉解析未成功 (状态码 {r_gen.status_code}): {r_gen.text[:200]}"

            res_data = r_gen.json()
            parts = res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            output_text = ""
            for p in parts:
                if not p.get("thought") and p.get("text"):
                    output_text += p.get("text")

            if not output_text:
                return "大模型已观看完毕，但未生成解析文本喵。"

            header_info = f"🎬 【小橘深度视频视评】: 《{meta['title']}》 (UP主: {meta['owner']})\n------------------------------------\n"
            return header_info + output_text

        except Exception as e:
            return f"多模态视频解析链路异常: {e}"
        finally:
            if Path(slim_path).exists():
                try:
                    Path(slim_path).unlink(missing_ok=True)
                except Exception:
                    pass
