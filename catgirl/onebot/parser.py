# -*- coding: utf-8 -*-
"""
OneBot 11 消息与富文本解析器
支持 CQ 码提取、QQ 原生黄脸表情映射、引用回复消息与合并转发树递归提取
"""

import re
import html
from typing import Tuple, List
from .client import call_api

QQ_FACE_MAP = {
    "178": "[滑稽]", "14": "[微笑]", "1": "[撇嘴]", "2": "[色]", "3": "[发呆]",
    "4": "[得意]", "5": "[流泪]", "6": "[害羞]", "7": "[闭嘴]", "8": "[睡]",
    "9": "[大哭]", "10": "[尴尬]", "11": "[发怒]", "12": "[调皮]", "13": "[呲牙]",
    "21": "[白眼]", "24": "[难过]", "26": "[抓狂]", "27": "[吐]", "28": "[偷笑]",
    "29": "[可爱]", "32": "[饥饿]", "33": "[困]", "34": "[惊恐]", "35": "[流汗]",
    "36": "[憨笑]", "38": "[奋斗]", "39": "[咒骂]", "40": "[疑问]", "41": "[嘘]",
    "42": "[晕]", "43": "[折磨]", "44": "[衰]", "45": "[骷髅]", "46": "[敲打]",
    "47": "[再见]", "48": "[擦汗]", "49": "[抠鼻]", "50": "[鼓掌]", "53": "[坏笑]",
    "54": "[左哼哼]", "55": "[右哼哼]", "56": "[哈欠]", "57": "[鄙视]", "58": "[委屈]",
    "59": "[快哭了]", "60": "[阴险]", "61": "[亲亲]", "62": "[吓]", "63": "[可怜]",
    "64": "[菜刀]", "65": "[西瓜]", "66": "[啤酒]", "67": "[咖啡]", "68": "[饭]",
    "69": "[猪头]", "70": "[玫瑰]", "71": "[凋谢]", "72": "[示爱]", "73": "[爱心]",
    "74": "[心碎]", "75": "[蛋糕]", "76": "[闪电]", "77": "[炸弹]", "78": "[刀]",
    "79": "[足球]", "80": "[瓢虫]", "81": "[便便]", "82": "[月亮]", "83": "[太阳]",
    "84": "[礼物]", "85": "[拥抱]", "86": "[强]", "87": "[弱]", "88": "[握手]",
    "89": "[胜利]", "90": "[抱拳]", "96": "[差劲]", "97": "[爱你]", "98": "[NO]",
    "99": "[OK]", "100": "[爱情]", "101": "[飞吻]", "102": "[跳跳]", "103": "[发抖]",
    "104": "[怄火]", "105": "[转圈]", "106": "[磕头]", "107": "[回头]", "108": "[跳绳]",
    "109": "[挥手]", "172": "[托腮]", "173": "[摸头]", "174": "[警戒]", "175": "[狂汗]",
    "176": "[泪奔]", "177": "[无奈]", "179": "[喜极而泣]", "180": "[吐舌]", "181": "[泪目]",
    "182": "[瞟]", "183": "[困惑]", "184": "[叹气]", "187": "[苦笑]", "212": "[敬礼]",
    "277": "[狗头]", "281": "[汪汪]", "318": "[摸鱼]", "320": "[摊手]", "324": "[喵喵]"
}

def decode_qq_face(face_id: str) -> str:
    """将 QQ 原生表情 ID 解码为直观的文本标签 (如 178 -> [滑稽])"""
    return QQ_FACE_MAP.get(str(face_id), f"[表情#{face_id}]")

def extract_clean_text(raw_msg, raw_str=""):
    text = ""
    if isinstance(raw_msg, list):
        parts = []
        for seg in raw_msg:
            if isinstance(seg, dict) and seg.get("type") == "text":
                parts.append(seg.get("data", {}).get("text", ""))
        text = "".join(parts).strip()
    elif isinstance(raw_msg, str):
        text = re.sub(r"\[CQ:[^]]+\]", "", raw_msg).strip()
    if not text and raw_str:
        text = re.sub(r"\[CQ:[^]]+\]", "", raw_str).strip()
    return text


def extract_text_from_segments(segments):
    lines = []
    for s in segments:
        if not isinstance(s, dict): continue
        st = s.get("type")
        sd = s.get("data", {}) or {}
        if st == "text":
            t = sd.get("text", "").strip()
            if t: lines.append(t)
        elif st == "at":
            qq = sd.get("qq", "")
            lines.append(f"@{qq}")
        elif st == "image":
            lines.append("[图片]")
    return " ".join(lines).strip()

async def get_msg_content(ws, msg_id):
    resp = await call_api(ws, "get_msg", {"message_id": msg_id})
    if not resp or resp.get("status") != "ok": return "", []
    data = resp.get("data", {})
    message_content = data.get("message", [])
    raw_str = data.get("raw_message", "")
    sub_imgs = []
    if isinstance(message_content, list):
        for s in message_content:
            if not isinstance(s, dict): continue
            if s.get("type") == "image":
                u = s.get("data", {}).get("url") or s.get("data", {}).get("file") or ""
                if isinstance(u, str) and u.startswith("http"):
                    sub_imgs.append(html.unescape(u).strip())
    if raw_str:
        for m in re.finditer(r"\[CQ:image,[^]]*url=([^,\]]+)", raw_str):
            sub_imgs.append(html.unescape(m.group(1)).strip())
    dedup_imgs = list(dict.fromkeys(sub_imgs))
    text = ""
    if isinstance(message_content, list):
        text = extract_text_from_segments(message_content)
    if not text and raw_str:
        text = re.sub(r"\[CQ:[^]]+\]", "", raw_str).strip()
    return text, dedup_imgs

async def get_forward_content(ws, forward_id):
    resp = await call_api(ws, "get_forward_msg", {"id": forward_id})
    if not resp or resp.get("status") != "ok": return "", []
    messages = resp.get("data", {}).get("messages", [])
    lines = []
    forward_images = []
    for m in messages[:8]:
        s_name = m.get("sender", {}).get("nickname", "某人")
        msg_body = m.get("message")
        m_raw = m.get("raw_message", "")
        f_imgs = []
        if isinstance(msg_body, list):
            for s in msg_body:
                if isinstance(s, dict) and s.get("type") == "image":
                    u = s.get("data", {}).get("url") or s.get("data", {}).get("file") or ""
                    if isinstance(u, str) and u.startswith("http"):
                        f_imgs.append(html.unescape(u).strip())
        if m_raw:
            for match in re.finditer(r"\[CQ:image,[^]]*url=([^,\]]+)", m_raw):
                f_imgs.append(html.unescape(match.group(1)).strip())
        for u in f_imgs:
            if u not in forward_images: forward_images.append(u)
        line_text = ""
        if isinstance(msg_body, list):
            line_text = extract_text_from_segments(msg_body)
        if not line_text and m_raw:
            line_text = re.sub(r"\[CQ:[^]]+\]", "", m_raw).strip()
        if f_imgs and not line_text:
            line_text = "[图片]"
        elif f_imgs:
            line_text += " [附图片]"
        if line_text:
            lines.append(f"{s_name}: {line_text}")
    return "【合并转发内容】:\n" + "\n".join(lines), forward_images

