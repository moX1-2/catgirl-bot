# -*- coding: utf-8 -*-
"""
群聊上下文流动记忆管理器与多模态表情包视觉缓冲池
"""

import re
import html
import time
from collections import defaultdict, deque
from typing import Tuple, List, Optional
from ..config import BOT_QQ
from .client import call_api
from .parser import extract_clean_text

# 群聊实时消息环形缓冲区 (内存中每个群最多保留 30 条)
group_recent_messages = defaultdict(lambda: deque(maxlen=30))

def record_recent_group_message(event):
    group_id = event.get("group_id")
    if not group_id: return
    user_id = event.get("user_id")
    sender_name = event.get("sender", {}).get("card") or event.get("sender", {}).get("nickname") or f"QQ{user_id}"
    msg_id = event.get("message_id")
    raw_msg = event.get("message", [])
    raw_str = event.get("raw_message", "")
    
    img_urls = []
    if isinstance(raw_msg, list):
        for seg in raw_msg:
            if isinstance(seg, dict):
                st = seg.get("type")
                sd = seg.get("data", {}) or {}
                if st in ["image", "mface", "marketface", "bface"]:
                    u = sd.get("url") or sd.get("file") or ""
                    if isinstance(u, str) and u.startswith("http"):
                        clean_u = html.unescape(u).strip()
                        if clean_u not in img_urls: img_urls.append(clean_u)
    if raw_str:
        for m in re.finditer(r"\[CQ:(?:image|mface|marketface)[^]]*url=([^,\]]+)", raw_str):
            clean_u = html.unescape(m.group(1)).strip()
            if clean_u not in img_urls: img_urls.append(clean_u)

    clean_txt = extract_clean_text(raw_msg, raw_str)
    if img_urls and not clean_txt:
        clean_txt = "[表情包/图片]"
    elif img_urls:
        clean_txt = f"{clean_txt} [附表情包/图片]"

    if clean_txt or img_urls:
        group_recent_messages[group_id].append({
            "message_id": msg_id,
            "sender_name": sender_name,
            "text": clean_txt,
            "image_urls": img_urls,
            "time": time.time()
        })

async def fetch_recent_group_context(ws, group_id, current_msg_id=None, limit=20):
    """
    拉取最近上下文，同时收集最近出现的表情包/图片链接（供无图提问时回溯视觉）
    """
    records = []
    context_images = []

    resp = await call_api(ws, "get_group_msg_history", {"group_id": group_id, "count": limit + 2}, timeout=3.5)
    if resp and resp.get("status") == "ok" and isinstance(resp.get("data"), dict):
        messages = resp["data"].get("messages", [])
        for m in messages:
            m_id = m.get("message_id")
            if current_msg_id and m_id == current_msg_id: continue
            u_id = m.get("user_id")
            name = "阿橘(你自身)" if str(u_id) == str(BOT_QQ) else (m.get("sender", {}).get("card") or m.get("sender", {}).get("nickname") or f"QQ{u_id}")
            
            m_imgs = []
            if isinstance(m.get("message"), list):
                for seg in m.get("message"):
                    if isinstance(seg, dict) and seg.get("type") in ["image", "mface", "marketface", "bface"]:
                        u = seg.get("data", {}).get("url") or seg.get("data", {}).get("file") or ""
                        if isinstance(u, str) and u.startswith("http"):
                            clean_u = html.unescape(u).strip()
                            if clean_u not in m_imgs: m_imgs.append(clean_u)
            if m.get("raw_message"):
                for match in re.finditer(r"\[CQ:(?:image|mface|marketface)[^]]*url=([^,\]]+)", m.get("raw_message")):
                    clean_u = html.unescape(match.group(1)).strip()
                    if clean_u not in m_imgs: m_imgs.append(clean_u)

            txt = extract_clean_text(m.get("message"), m.get("raw_message", ""))
            if m_imgs and not txt:
                txt = "[表情包/图片]"
            elif m_imgs:
                txt = f"{txt} [附表情包/图片]"

            if txt:
                records.append(f"- {name}: {txt}")
                for img_u in m_imgs:
                    if img_u not in context_images:
                        context_images.append(img_u)

    if not records and group_id in group_recent_messages:
        for m in list(group_recent_messages[group_id]):
            if current_msg_id and m.get("message_id") == current_msg_id: continue
            records.append(f"- {m['sender_name']}: {m['text']}")
            for img_u in m.get("image_urls", []):
                if img_u not in context_images:
                    context_images.append(img_u)

    text_ctx = ""
    if records:
        trimmed = records[-limit:]
        text_ctx = "【群聊最近上下文背景 (供参考当前话题，不代表直接问你)】:\n" + "\n".join(trimmed)

    # 取最近的最多 3 张表情包/图片
    recent_3_imgs = context_images[-3:] if context_images else []
    return text_ctx, recent_3_imgs

