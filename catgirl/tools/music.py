# -*- coding: utf-8 -*-
"""
纯原声音乐检索与音频点歌引擎
通过配置化音源曲库检索歌曲直链，配合 QQ 原生专属母带级音质增强管线 (Audiophile Silk Mastering)，
直接作为 QQ 原生语音气泡下发给群聊或私聊，享受零卡片拦截、高保真无破音的极简点歌体验。
音源端点与请求凭证全面支持通过环境变量自定义注入，保持开源代码通用与合规。
"""

import os
import time
import json
import string
import secrets
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import requests

CACHE_DIR = Path("/tmp/catgirl_music_cache")
MAX_CACHE_FILES = 30
MAX_CACHE_SIZE_BYTES = 150 * 1024 * 1024  # 150 MB

TRACK_USER_ALPHABET = string.ascii_lowercase + string.digits
_music_lock = asyncio.Lock()


def _ensure_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _clean_old_cache():
    """自动清理过旧的音乐缓存，防止占满磁盘"""
    try:
        if not CACHE_DIR.exists():
            return
        files = list(CACHE_DIR.glob("*.mp3"))
        if len(files) <= MAX_CACHE_FILES:
            total_size = sum(f.stat().st_size for f in files)
            if total_size <= MAX_CACHE_SIZE_BYTES:
                return

        # 按最后修改时间排序，清理最旧的文件
        files.sort(key=lambda f: f.stat().st_mtime)
        while len(files) > MAX_CACHE_FILES // 2:
            f = files.pop(0)
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as e:
        print(f"[-] 清理音乐缓存异常: {e}")


def _optimize_for_qq_voice(input_path: str, output_path: str) -> bool:
    """
    针对 QQ 语音 (Silk v3 超宽带 24kHz) 执行专属母带级声学增强：
    1. volume=-1.8dB: 动态余量保护，彻底消灭双声道混合导致的数字削波破音与爆音
    2. highpass=f=35: 滤除 35Hz 以下无意义次低频泥沼，人声与鼓点更加紧实干净
    3. lowpass=f=11800: 抗混叠低通砖墙滤波，消除 24kHz 降采样折射回来的金属铁皮杂音
    4. -ar 24000 -ac 1: 完美契合 QQ 语音底层采样率，由 ffmpeg 专业级插值重混
    """
    try:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", "highpass=f=35,lowpass=f=11800,volume=-1.8dB",
            "-ar", "24000",
            "-ac", "1",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            output_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000
    except Exception as e:
        print(f"[-] ffmpeg 母带预处理异常 (将回退原文件): {e}")
        return False


def _search_primary_source(keyword: str) -> Optional[Dict[str, Any]]:
    """从主音源服务检索歌曲 (端点由环境变量注入，优先获取 320kbps 极高音质母带)"""
    search_url = os.getenv("MUSIC_SEARCH_URL", "").strip()
    track_url = os.getenv("MUSIC_TRACK_URL", "").strip()
    app_source = os.getenv("MUSIC_APP_SOURCE", "").strip()

    if not search_url or not track_url:
        return None

    search_params = {
        "allpay": 1,
        "all": keyword,
        "pn": 0,
        "rn": 3,
        "vipver": 1,
        "show_copyright_off": 1,
        "correct": 1,
        "ft": "music",
        "encoding": "utf8",
        "rformat": "json",
        "vermerge": 1,
        "mobi": 1,
        "issubtitle": 1,
    }
    try:
        r = requests.get(search_url, params=search_params, timeout=6)
        data = r.json()
        abslist = data.get("abslist", [])
        if not abslist:
            return None
        song = abslist[0]
        rid = song.get("MUSICRID", "").replace("MUSIC_", "")
        title = song.get("SONGNAME", "")
        artist = song.get("ARTIST", "")
        album = song.get("ALBUM", "")

        # 优先请求 320kbps 极高品质母带以保留完整泛音细节，若无则回退 128k
        direct_url = None
        duration = 0
        for target_br in ["320kmp3", "128kmp3"]:
            user = "".join(secrets.choice(TRACK_USER_ALPHABET) for _ in range(16))
            track_params = {
                "f": "web",
                "source": app_source,
                "type": "convert_url_with_sign",
                "rid": rid,
                "br": target_br,
                "user": user,
            }
            tr = requests.get(track_url, params=track_params, timeout=6)
            tdata = tr.json()
            cand_url = tdata.get("data", {}).get("url")
            if cand_url and cand_url.startswith("http"):
                direct_url = cand_url
                duration = tdata.get("data", {}).get("duration", 0)
                print(f"[+] 成功捕获音源直链 (质量档位: {target_br})")
                break

        if direct_url:
            return {
                "source": "primary",
                "rid": rid,
                "title": title,
                "artist": artist,
                "album": album,
                "url": direct_url,
                "duration": duration,
            }
    except Exception as e:
        print(f"[-] 主音源检索异常: {e}")
    return None


def _search_fallback_source(keyword: str) -> Optional[Dict[str, Any]]:
    """备用公开音源检索 (网易云开放接口)"""
    search_url = os.getenv("MUSIC_FALLBACK_URL", "https://music.163.com/api/search/get/web").strip()
    params = {"s": keyword, "type": 1, "offset": 0, "limit": 3}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://music.163.com/",
    }
    try:
        r = requests.post(search_url, data=params, headers=headers, timeout=6)
        songs = r.json().get("result", {}).get("songs", [])
        for s in songs:
            sid = s.get("id")
            title = s.get("name")
            artists = "/".join([a["name"] for a in s.get("artists", [])])
            album = s.get("album", {}).get("name", "")
            outer_url = f"http://music.163.com/song/media/outer/url?id={sid}.mp3"

            h = requests.head(outer_url, allow_redirects=True, timeout=5)
            size = int(h.headers.get("Content-Length", 0))
            if h.status_code == 200 and size > 200000:
                return {
                    "source": "fallback",
                    "rid": str(sid),
                    "title": title,
                    "artist": artists,
                    "album": album,
                    "url": outer_url,
                    "duration": s.get("duration", 0) // 1000,
                }
    except Exception as e:
        print(f"[-] 备用音源检索异常: {e}")
    return None


async def search_and_download_music(keyword: str) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    检索、下载并经过高保真声学优化管线处理。
    返回 (local_audio_path, song_meta, error_msg)
    """
    clean_kw = keyword.strip()
    if not clean_kw:
        return None, None, "未提供歌曲关键词"

    cache_dir = _ensure_cache_dir()
    _clean_old_cache()

    async with _music_lock:
        print(f"[*] 正在为关键词 '{clean_kw}' 检索音源...")
        loop = asyncio.get_running_loop()

        # 1. 优先检索配置的主音源 (最高 320kbps)
        song_meta = await loop.run_in_executor(None, _search_primary_source, clean_kw)
        # 2. 备用检索公开音源
        if not song_meta:
            print(f"[*] 主音源未命中或未配置，尝试备用音源检索...")
            song_meta = await loop.run_in_executor(None, _search_fallback_source, clean_kw)

        if not song_meta or not song_meta.get("url"):
            return None, None, f"未能在曲库中找到与《{clean_kw}》匹配的可用音源"

        rid = song_meta.get("rid", "unknown")
        raw_path = cache_dir / f"{song_meta['source']}_{rid}_raw.mp3"
        mastered_path = cache_dir / f"{song_meta['source']}_{rid}.mp3"

        # 检查本地是否已有优化后的母带缓存
        if mastered_path.exists() and mastered_path.stat().st_size > 100000:
            print(f"[+] 命中音乐高清母带缓存: {mastered_path} ({mastered_path.stat().st_size} bytes)")
            return str(mastered_path), song_meta, None

        # 3. 下载原始母带音频 (User-Agent 支持环境变量配置)
        def _download_and_master():
            ua = os.getenv("MUSIC_DOWNLOAD_UA", "Mozilla/5.0").strip()
            headers = {
                "User-Agent": ua,
                "Accept-Encoding": "identity",
            }
            resp = requests.get(song_meta["url"], headers=headers, timeout=25)
            if resp.status_code == 200 and len(resp.content) > 100000:
                with open(raw_path, "wb") as f:
                    f.write(resp.content)
                
                # 4. 执行 QQ 原生专属母带级音质增强与防破音处理
                print(f"[*] 正在执行 Silk 母带级抗削波与高清抗混叠优化...")
                ok = _optimize_for_qq_voice(str(raw_path), str(mastered_path))
                if ok:
                    try:
                        raw_path.unlink(missing_ok=True)  # 清理体积庞大的 raw 源文件
                    except Exception:
                        pass
                    return True
                else:
                    # 若 ffmpeg 优化因不可抗力失败，直接使用原始文件兜底
                    os.replace(str(raw_path), str(mastered_path))
                    return True
            return False

        success = await loop.run_in_executor(None, _download_and_master)
        if success and mastered_path.exists():
            print(f"[+] 高保真音频就绪: {mastered_path} ({mastered_path.stat().st_size} bytes)")
            return str(mastered_path), song_meta, None
        else:
            return None, song_meta, "音频流下载失败或文件异常"
