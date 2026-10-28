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



def clean_markdown_for_qq(text: str) -> str:
    """
    将大模型生成的 Markdown 文本清洗转换为优雅、易读的 QQ 原生纯文本
    1. 剥离残留的裸 SVG XML 代码
    2. 转换 Markdown 超链接 [名称](URL) -> 名称 (URL)
    3. 转换代码块为清晰的纯文本分割线
    4. 转换行内代码 `code` 为 「code」
    5. 转换 **加粗** 与 __加粗__ 为 【重点】
    6. 转换 # 标题 为 【标题】
    7. 转换列表符号 (*, -, +) 为圆点 ·
    8. 规范过长的空白换行
    """
    if not text:
        return ""

    s = text.strip()

    # 1. 剥离残留 SVG
    s = re.sub(r"```(?:xml|svg)?\s*<svg[\s\S]*?</svg>\s*```", "", s, flags=re.I)
    s = re.sub(r"<svg[\s\S]*?</svg>", "", s, flags=re.I)

    # 2. Markdown 超链接: [说明](url) -> 说明 (url)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\1 (\2)", s)

    # 3. 多行代码块: ```lang ... ```
    def _code_block_sub(m):
        code_body = m.group(1).strip()
        return f"\n----- [代码片段] -----\n{code_body}\n--------------------\n"
    s = re.sub(r"```[a-zA-Z0-9_-]*\n([\s\S]*?)\n```", _code_block_sub, s)
    s = re.sub(r"```([\s\S]*?)```", _code_block_sub, s)

    # 4. 行内代码: `code` -> 「code」
    s = re.sub(r"`([^`\n]+)`", r"「\1」", s)

    # 5. 加粗与斜体:
    # ***加粗斜体*** -> 【内容】
    s = re.sub(r"\*\*\*([^*\n]+)\*\*\*", r"【\1】", s)
    # **加粗** -> 【内容】
    s = re.sub(r"\*\*([^*\n]+)\*\*", r"【\1】", s)
    # __加粗__ -> 【内容】
    s = re.sub(r"__([^_\n]+)__", r"【\1】", s)
    # *斜体* -> 内容 (剥离孤立单星号)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", s)

    # 6. 各级标题: # 标题 -> 【标题】
    s = re.sub(r"^#{1,6}\s*(.+)$", r"【\1】", s, flags=re.M)

    # 7. 无序列表: *, -, + -> · 
    s = re.sub(r"^[\*\-\+]\s+", r"· ", s, flags=re.M)

    # 8. 引用块: > 引用 -> | 引用
    s = re.sub(r"^>\s*(.+)$", r"| \1", s, flags=re.M)

    # 9. 分割线: --- 或 *** -> --------------------
    s = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", r"--------------------", s, flags=re.M)

    # 10. 压缩 3 个以上的连续换行
    s = re.sub(r"\n{3,}", "\n\n", s)

    return s.strip()

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


async def get_forward_content(ws, forward_id, depth=0, max_depth=3):
    """
    递归解构合并转发消息 (全面支持嵌套合并转发、嵌套图包、多层嵌套)
    """
    if depth > max_depth:
        return "", []

    resp = await call_api(ws, "get_forward_msg", {"id": str(forward_id)})
    if not resp or resp.get("status") != "ok":
        return "", []

    messages = resp.get("data", {}).get("messages", [])
    lines = []
    forward_images = []

    async def parse_node_list(nodes, sub_depth):
        if sub_depth > max_depth:
            return

        for m in nodes[:25]:
            s_name = (m.get("sender") or {}).get("card") or (m.get("sender") or {}).get("nickname") or "某人"
            msg_body = m.get("message")
            m_raw = m.get("raw_message", "")

            node_imgs = []
            node_texts = []

            # 1. 结构化 message 数组解析
            if isinstance(msg_body, list):
                for s in msg_body:
                    if not isinstance(s, dict): continue
                    st = s.get("type")
                    sd = s.get("data", {}) or {}

                    if st in ["image", "mface", "marketface", "bface"]:
                        u = sd.get("url") or ""
                        f = sd.get("file") or ""
                        if u and isinstance(u, str) and u.startswith("http"):
                            node_imgs.append(html.unescape(u).strip())
                        elif f and isinstance(f, str):
                            if f.startswith("http"):
                                node_imgs.append(html.unescape(f).strip())
                            else:
                                try:
                                    img_r = await call_api(ws, "get_image", {"file": f}, timeout=2.5)
                                    if img_r and isinstance(img_r.get("data"), dict) and img_r["data"].get("url"):
                                        direct_url = html.unescape(img_r["data"]["url"]).strip()
                                        if direct_url.startswith("http"):
                                            node_imgs.append(direct_url)
                                except Exception:
                                    pass

                    elif st == "forward":
                        # 核心突破：递归解构嵌套合并转发/嵌套图包
                        sub_content = sd.get("content")
                        if isinstance(sub_content, list) and sub_content:
                            await parse_node_list(sub_content, sub_depth + 1)
                        elif sd.get("id"):
                            _, sub_imgs = await get_forward_content(ws, sd["id"], sub_depth + 1, max_depth)
                            node_imgs.extend(sub_imgs)

                    elif st == "node":
                        sub_content = sd.get("content") or sd.get("message")
                        if isinstance(sub_content, list) and sub_content:
                            await parse_node_list(sub_content, sub_depth + 1)

                    elif st == "text":
                        t = sd.get("text", "").strip()
                        if t: node_texts.append(t)

            # 2. CQ 码兜底 (提取内嵌 forward 与 image)
            if m_raw:
                for match in re.finditer(r"\[CQ:(?:image|mface|marketface)[^]]*url=([^,\]]+)", m_raw):
                    clean_u = html.unescape(match.group(1)).strip()
                    if clean_u not in node_imgs: node_imgs.append(clean_u)

                for match in re.finditer(r"\[CQ:forward,id=([^,\]]+)\]", m_raw):
                    nested_fid = match.group(1).strip()
                    if nested_fid != str(forward_id):
                        _, sub_imgs = await get_forward_content(ws, nested_fid, sub_depth + 1, max_depth)
                        for u in sub_imgs:
                            if u not in node_imgs: node_imgs.append(u)

            for u in node_imgs:
                if u not in forward_images:
                    forward_images.append(u)

            txt = " ".join(node_texts).strip()
            if node_imgs and not txt:
                txt = f"[图包图片 x{len(node_imgs)}]"
            elif node_imgs:
                txt += f" [附图 x{len(node_imgs)}]"

            if txt:
                lines.append(f"{s_name}: {txt}")

    await parse_node_list(messages, depth)
    summary_header = "【嵌套合并转发图包内容】:" if depth > 0 else "【合并转发内容】:"
    return summary_header + "\n" + "\n".join(lines[:25]), forward_images

async def get_msg_content(ws, msg_id):
    """
    获取单条消息内容并提取图片与嵌套合并转发
    """
    resp = await call_api(ws, "get_msg", {"message_id": msg_id})
    if not resp or resp.get("status") != "ok": return "", []
    data = resp.get("data", {})
    message_content = data.get("message", [])
    raw_str = data.get("raw_message", "")
    sub_imgs = []

    if isinstance(message_content, list):
        for s in message_content:
            if not isinstance(s, dict): continue
            st = s.get("type")
            sd = s.get("data", {}) or {}
            if st in ["image", "mface", "marketface", "bface"]:
                u = sd.get("url") or sd.get("file") or ""
                if isinstance(u, str) and u.startswith("http"):
                    sub_imgs.append(html.unescape(u).strip())
                elif sd.get("file"):
                    try:
                        img_r = await call_api(ws, "get_image", {"file": sd["file"]}, timeout=2.5)
                        if img_r and isinstance(img_r.get("data"), dict) and img_r["data"].get("url"):
                            direct_u = html.unescape(img_r["data"]["url"]).strip()
                            if direct_u.startswith("http"):
                                sub_imgs.append(direct_u)
                    except Exception:
                        pass
            elif st == "forward":
                fid = sd.get("id")
                if fid:
                    _, f_imgs = await get_forward_content(ws, fid)
                    sub_imgs.extend(f_imgs)

    if raw_str:
        for m in re.finditer(r"\[CQ:(?:image|mface|marketface)[^]]*url=([^,\]]+)", raw_str):
            sub_imgs.append(html.unescape(m.group(1)).strip())
        for m in re.finditer(r"\[CQ:forward,id=([^,\]]+)\]", raw_str):
            fid = m.group(1).strip()
            _, f_imgs = await get_forward_content(ws, fid)
            sub_imgs.extend(f_imgs)

    dedup_imgs = list(dict.fromkeys(sub_imgs))
    text = ""
    if isinstance(message_content, list):
        text = extract_text_from_segments(message_content)
    if not text and raw_str:
        text = re.sub(r"\[CQ:[^]]+\]", "", raw_str).strip()
    return text, dedup_imgs
