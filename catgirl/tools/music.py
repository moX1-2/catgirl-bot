# -*- coding: utf-8 -*-
"""
纯原声音乐检索与音频点歌引擎 (支持多候选透视与副歌起唱智能分析)
解决盲选 Top-1 导致的召回偏离断层，支持候选列表审查、副歌起唱秒数探测，
配合 QQ 原生专属母带级音质增强管线 (Audiophile Silk Mastering)，
零卡片拦截、高保真无破音。
"""

import os
import re
import time
import json
import string
import secrets
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
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
    """针对 QQ 语音 (Silk v3 超宽带 24kHz) 执行专属母带级声学增强与防破音削波"""
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


def _clean_html_entities(text: str) -> str:
    """清洗曲库返回的 &nbsp; 等 HTML 转义字符"""
    if not text:
        return ""
    t = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", "\"").replace("&apos;", "'")
    return re.sub(r"\s+", " ", t).strip()


def search_music_candidates_sync(keyword: str, limit: int = 6) -> List[Dict[str, Any]]:
    """
    检索曲库候选版本列表，带有副歌时间点与时长元数据，供大模型精准挑选版本。
    彻底解决盲选 Top-1 导致的‘意图识别对但召回不对’问题。
    """
    search_url = os.getenv("MUSIC_SEARCH_URL", "").strip()
    if not search_url:
        return []

    clean_kw = keyword.strip()
    # 智能分词容错：若关键词过长，去除干扰助词
    search_terms = [clean_kw]
    # 若包含“开头是...”、“有一版...”等自然语言修饰，提取前后的核心歌名与修饰词
    core_kw = re.sub(r"(开头是|有一版|带|要|放首|来首|听|那首)[^ ]*", "", clean_kw).strip()
    if core_kw and core_kw != clean_kw:
        search_terms.append(core_kw)

    candidates = []
    seen_rids = set()

    for term in search_terms:
        params = {
            "allpay": 1,
            "all": term,
            "pn": 0,
            "rn": limit,
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
            r = requests.get(search_url, params=params, timeout=6)
            try:
                data = r.json()
            except Exception:
                data = json.loads(r.text.replace("'", '"'))

            abslist = data.get("abslist", [])
            for s in abslist:
                rid = s.get("MUSICRID", "").replace("MUSIC_", "").strip()
                if not rid or rid in seen_rids:
                    continue
                seen_rids.add(rid)

                raw_name = _clean_html_entities(s.get("SONGNAME", ""))
                artist = _clean_html_entities(s.get("ARTIST", ""))
                album = _clean_html_entities(s.get("ALBUM", ""))
                duration_sec = int(s.get("DURATION", 0))
                dur_min = duration_sec // 60
                dur_sec = duration_sec % 60
                dur_str = f"{dur_min}分{dur_sec:02d}秒" if duration_sec > 0 else "未知"

                # 提取副歌起唱秒数
                pay_info = s.get("payInfo", {})
                refrain_start = 0
                if isinstance(pay_info, dict):
                    try:
                        refrain_start = int(pay_info.get("refrain_start", 0))
                    except Exception:
                        refrain_start = 0

                refrain_desc = "0秒 (副歌直接开门见山/无长前奏)" if refrain_start == 0 else f"{refrain_start}秒"

                candidates.append({
                    "rid": rid,
                    "title": raw_name,
                    "artist": artist,
                    "album": album,
                    "duration_sec": duration_sec,
                    "duration_str": dur_str,
                    "refrain_start": refrain_start,
                    "refrain_desc": refrain_desc,
                    "source": "primary"
                })
                if len(candidates) >= limit:
                    break
        except Exception as e:
            print(f"[-] 检索候选异常: {e}")

        if len(candidates) >= limit:
            break

    return candidates


def _get_direct_url_for_rid(rid: str) -> Optional[Tuple[str, int]]:
    """为指定 rid 获取 320k/128k 音频直链与时长"""
    track_url = os.getenv("MUSIC_TRACK_URL", "").strip()
    app_source = os.getenv("MUSIC_APP_SOURCE", "").strip()
    if not track_url:
        return None

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
        try:
            tr = requests.get(track_url, params=track_params, timeout=6)
            tdata = tr.json()
            cand_url = tdata.get("data", {}).get("url")
            duration = tdata.get("data", {}).get("duration", 0)
            if cand_url and cand_url.startswith("http"):
                print(f"[+] 成功捕获直链 rid={rid} (档位: {target_br})")
                return cand_url, duration
        except Exception:
            pass
    return None


async def search_candidates_tool(keyword: str, limit: int = 5) -> str:
    """
    Agent 工具函数：曲库多版本候选检索。
    返回结构化的候选版本清单，暴露歌名标签、歌手、时长与副歌开唱时间点。
    """
    clean_kw = keyword.strip()
    if not clean_kw:
        return "请提供要检索的歌曲关键词喵~"

    loop = asyncio.get_running_loop()
    candidates = await loop.run_in_executor(None, search_music_candidates_sync, clean_kw, limit)
    if not candidates:
        return f"在曲库中未检索到与《{clean_kw}》相关的版本喵~"

    lines = [f"【曲库为《{clean_kw}》检索到 {len(candidates)} 个候选版本】:"]
    for idx, c in enumerate(candidates, 1):
        lines.append(
            f"[{idx}] 《{c['title']}》 - {c['artist']} | 时长: {c['duration_str']} | "
            f"副歌起唱点: {c['refrain_desc']} | 编号ID: {c['rid']}"
        )
    lines.append(
        "💡 决策指引: 审阅上述候选的标题后缀（如DJ版、卡点版、副歌版）与副歌起唱点。\n"
        "如群友需要开门见山直接唱副歌的版本，优先挑选副歌起唱点为0秒且标题包含卡点/副歌的候选编号ID，"
        "并立即调用 play_music(music_id='选中的编号ID') 进行精准下发！"
    )
    return "\n".join(lines)


async def search_and_download_music(
    keyword: str = "",
    music_id: Optional[str] = None
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    检索、下载并经过高保真声学优化管线处理。
    既支持传入特定 music_id 精准播发，也支持普通关键词模糊播发。
    返回 (local_audio_path, song_meta, error_msg)
    """
    cache_dir = _ensure_cache_dir()
    _clean_old_cache()

    async with _music_lock:
        loop = asyncio.get_running_loop()
        target_rid = (music_id or "").strip()
        song_meta = None

        # 1. 如果传入了特定 music_id，直接走精准定位
        if target_rid:
            print(f"[*] 执行指定编号 ID 精准定位: rid={target_rid}")
            res = await loop.run_in_executor(None, _get_direct_url_for_rid, target_rid)
            if res:
                url, duration = res
                song_meta = {
                    "source": "primary",
                    "rid": target_rid,
                    "title": keyword or f"歌曲 {target_rid}",
                    "artist": "",
                    "album": "",
                    "url": url,
                    "duration": duration,
                }
            else:
                return None, None, f"编号为 {target_rid} 的音源直链解析失败"
        else:
            # 2. 普通关键词检索：优先多候选第一条或智能重排
            clean_kw = keyword.strip()
            if not clean_kw:
                return None, None, "未提供歌曲关键词或编号ID"

            print(f"[*] 正在为关键词 '{clean_kw}' 检索音源...")
            candidates = await loop.run_in_executor(None, search_music_candidates_sync, clean_kw, 5)
            if candidates:
                chosen = candidates[0]
                target_rid = chosen["rid"]
                res = await loop.run_in_executor(None, _get_direct_url_for_rid, target_rid)
                if res:
                    url, duration = res
                    song_meta = {
                        "source": "primary",
                        "rid": target_rid,
                        "title": chosen["title"],
                        "artist": chosen["artist"],
                        "album": chosen["album"],
                        "url": url,
                        "duration": duration or chosen["duration_sec"],
                    }

        if not song_meta or not song_meta.get("url"):
            return None, None, f"未能检索到可用的音频直链"

        rid = song_meta.get("rid", "unknown")
        raw_path = cache_dir / f"{song_meta['source']}_{rid}_raw.mp3"
        mastered_path = cache_dir / f"{song_meta['source']}_{rid}.mp3"

        # 命中母带缓存直接返回
        if mastered_path.exists() and mastered_path.stat().st_size > 100000:
            print(f"[+] 命中高清母带缓存: {mastered_path} ({mastered_path.stat().st_size} bytes)")
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
                        raw_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return True
                else:
                    os.replace(str(raw_path), str(mastered_path))
                    return True
            return False

        success = await loop.run_in_executor(None, _download_and_master)
        if success and mastered_path.exists():
            print(f"[+] 高保真音频就绪: {mastered_path} ({mastered_path.stat().st_size} bytes)")
            return str(mastered_path), song_meta, None
        else:
            return None, song_meta, "音频流下载失败或文件异常"
