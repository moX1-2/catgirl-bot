# -*- coding: utf-8 -*-
"""
纯原声音乐检索与音频点歌引擎
通过配置化音源曲库检索歌曲直链，将音频直接作为 QQ 原生语音气泡下发给群聊或私聊，
零卡片拦截风险，享受沉浸收听的极简点歌体验。
音源端点与请求凭证全面支持通过环境变量自定义注入，保持开源代码通用与合规。
"""

import os
import time
import json
import string
import secrets
import asyncio
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


def _search_primary_source(keyword: str) -> Optional[Dict[str, Any]]:
    """从主音源服务检索歌曲 (端点由环境变量注入)"""
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

        user = "".join(secrets.choice(TRACK_USER_ALPHABET) for _ in range(16))
        track_params = {
            "f": "web",
            "source": app_source,
            "type": "convert_url_with_sign",
            "rid": rid,
            "br": "128kmp3",
            "user": user,
        }
        tr = requests.get(track_url, params=track_params, timeout=6)
        tdata = tr.json()
        direct_url = tdata.get("data", {}).get("url")
        duration = tdata.get("data", {}).get("duration", 0)

        if direct_url and direct_url.startswith("http"):
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
    检索并下载歌曲到本地缓存。
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

        # 1. 优先检索配置的主音源
        song_meta = await loop.run_in_executor(None, _search_primary_source, clean_kw)
        # 2. 备用检索公开音源
        if not song_meta:
            print(f"[*] 主音源未命中或未配置，尝试备用音源检索...")
            song_meta = await loop.run_in_executor(None, _search_fallback_source, clean_kw)

        if not song_meta or not song_meta.get("url"):
            return None, None, f"未能在曲库中找到与《{clean_kw}》匹配的可用音源"

        rid = song_meta.get("rid", "unknown")
        local_path = cache_dir / f"{song_meta['source']}_{rid}.mp3"

        # 检查本地命中缓存
        if local_path.exists() and local_path.stat().st_size > 100000:
            print(f"[+] 命中音乐本地缓存: {local_path} ({local_path.stat().st_size} bytes)")
            return str(local_path), song_meta, None

        # 3. 下载音频文件 (User-Agent 支持环境变量自定义配置)
        def _download():
            ua = os.getenv("MUSIC_DOWNLOAD_UA", "Mozilla/5.0").strip()
            headers = {
                "User-Agent": ua,
                "Accept-Encoding": "identity",
            }
            resp = requests.get(song_meta["url"], headers=headers, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 100000:
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                return True
            return False

        success = await loop.run_in_executor(None, _download)
        if success and local_path.exists():
            print(f"[+] 音频下载成功: {local_path} ({local_path.stat().st_size} bytes)")
            return str(local_path), song_meta, None
        else:
            return None, song_meta, "音频流下载失败或文件异常"
