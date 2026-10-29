# -*- coding: utf-8 -*-
"""
事件派发与交互调度器
负责消息解析、速率拦截、指令分流、概率唤醒触发与多模态回复下发
"""

import re
import html
import random
from typing import Dict, Any

from ..config import (
    BOT_QQ,
    GROUP_SESSION_MODE,
    GROUP_CONTEXT_LIMIT,
    FISH_TRIGGER_PROBABILITY,
    FORWARD_FOLD_ENABLED,
    FORWARD_FOLD_THRESHOLD,
    FORWARD_FOLD_LINES
)
from ..limiter import dm_limiter, blacklist_manager
from ..onebot.client import (
    ws_send,
    call_api,
    ensure_friend_list_cached,
    cached_friend_ids
)
from ..onebot.parser import (
    decode_qq_face,
    clean_markdown_for_qq,
    get_msg_content,
    get_forward_content
)
from ..onebot.context import (
    record_recent_group_message,
    fetch_recent_group_context
)
from ..agent.loop import ask_llm
from .admin import handle_admin_or_help

async def process_message_event(ws, event: Dict[str, Any]):
    """处理 OneBot message 消息事件"""
    user_id = event.get("user_id")
    if str(user_id) == str(BOT_QQ):
        return

    # ---------- 黑名单拦截 (彻底防止 Bot 回声死循环与恶意刷屏) ----------
    if blacklist_manager.is_blocked(str(user_id)):
        return

    msg_type = event.get("message_type")
    # ---------- 陌生人私聊速率限制保护（一分钟 5 条） ----------
    if msg_type == "private":
        user_id_str = str(user_id)
        await ensure_friend_list_cached(ws)
        is_friend = (user_id_str in cached_friend_ids) or (user_id_str == str(BOT_QQ))
        allowed, notice = dm_limiter.check_and_record(user_id_str, is_friend=is_friend)
        if not allowed:
            print(f"[-] 触发陌生人私聊限速拦截: QQ={user_id_str}")
            await ws_send(ws, {
                "action": "send_private_msg",
                "params": {"user_id": user_id, "message": notice}
            })
            return

    message_segments = event.get("message", [])
    raw_text = event.get("raw_message", "").strip()
    sender = event.get("sender", {}).get("card") or event.get("sender", {}).get("nickname") or "群友"

    text_parts = []
    image_urls = []
    forward_ids = []
    reply_ids = []

    if isinstance(message_segments, list):
        for seg in message_segments:
            if not isinstance(seg, dict): continue
            seg_type = seg.get("type")
            seg_data = seg.get("data", {}) or {}
            if seg_type == "text":
                text_parts.append(seg_data.get("text", ""))
            elif seg_type == "face":
                fid = str(seg_data.get("id", ""))
                text_parts.append(decode_qq_face(fid))
            elif seg_type in ["image", "mface", "marketface", "bface"]:
                url = seg_data.get("url") or ""
                file_v = seg_data.get("file") or ""
                summary = seg_data.get("summary") or seg_data.get("text") or ""
                if summary:
                    clean_s = summary.strip().strip("[]")
                    if clean_s: text_parts.append(f"[{clean_s}]")
                if isinstance(url, str) and url.startswith("http"):
                    clean_u = html.unescape(url).strip()
                    if clean_u not in image_urls: image_urls.append(clean_u)
                elif file_v and isinstance(file_v, str):
                    if file_v.startswith("http"):
                        clean_u = html.unescape(file_v).strip()
                        if clean_u not in image_urls: image_urls.append(clean_u)
                    else:
                        try:
                            img_resp = await call_api(ws, "get_image", {"file": file_v}, timeout=3.0)
                            if img_resp and isinstance(img_resp.get("data"), dict):
                                direct_u = img_resp["data"].get("url")
                                if direct_u and direct_u.startswith("http"):
                                    clean_u = html.unescape(direct_u).strip()
                                    if clean_u not in image_urls: image_urls.append(clean_u)
                        except Exception as e:
                            print(f"[-] get_image 解析图片失败: {e}")
            elif seg_type == "forward":
                fid = seg_data.get("id")
                if fid: forward_ids.append(fid)
            elif seg_type == "reply":
                rid = seg_data.get("id")
                if rid: reply_ids.append(rid)

    # 提取 CQ 码兜底
    if raw_text:
        for m in re.finditer(r"\[CQ:face,id=(\d+)\]", raw_text):
            text_parts.append(decode_qq_face(m.group(1)))
        for m in re.finditer(r"\[CQ:(?:image|mface|marketface)[^]]*url=([^,\]]+)", raw_text):
            clean_u = html.unescape(m.group(1)).strip()
            if clean_u not in image_urls: image_urls.append(clean_u)
        for m in re.finditer(r"\[CQ:(?:image|mface|marketface)[^]]*file=([^,\]]+)", raw_text):
            f_val = m.group(1).strip()
            if not f_val.startswith("http") and not any(f_val in u for u in image_urls):
                try:
                    img_resp = await call_api(ws, "get_image", {"file": f_val}, timeout=3.0)
                    if img_resp and isinstance(img_resp.get("data"), dict):
                        direct_u = img_resp["data"].get("url")
                        if direct_u and direct_u.startswith("http"):
                            clean_u = html.unescape(direct_u).strip()
                            if clean_u not in image_urls: image_urls.append(clean_u)
                except Exception:
                    pass
        for m in re.finditer(r"\[CQ:forward,id=([^,\]]+)\]", raw_text):
            forward_ids.append(m.group(1))
        for m in re.finditer(r"\[CQ:reply,id=([^,\]]+)\]", raw_text):
            reply_ids.append(m.group(1))

    user_text = "".join(text_parts).strip()
    if not user_text and raw_text:
        user_text = re.sub(r"\[CQ:[^]]+\]", "", raw_text).strip()

    group_id = event.get("group_id")

    # ---------- 指令系统拦截 (0 Token 毫秒级直接响应) ----------
    intercepted = await handle_admin_or_help(ws, user_text, user_id, group_id, msg_type)
    if intercepted:
        return

    # ---------- 唤醒词与触发判定 ----------
    is_triggered = False
    if msg_type == "private":
        is_triggered = True
    elif msg_type == "group":
        record_recent_group_message(event)
        is_at = False
        if isinstance(message_segments, list):
            for s in message_segments:
                if isinstance(s, dict) and s.get("type") == "at" and str(s.get("data", {}).get("qq")) == str(BOT_QQ):
                    is_at = True
                    break
        if not is_at and raw_text and f"[CQ:at,qq={BOT_QQ}]" in raw_text:
            is_at = True

        # 1. 专属名字唤醒词：100% 触发响应
        direct_keywords = ["小橘", "阿橘", "橘宝", "猫猫", "喵喵"]
        has_direct_keyword = any(kw in user_text for kw in direct_keywords)

        # 2. 「鱼」关键词概率唤醒：投掷 0~1 随机数，仅 30% 概率触发
        fish_triggered = False
        if "鱼" in user_text and not has_direct_keyword and not is_at:
            roll = random.random()
            if roll < FISH_TRIGGER_PROBABILITY:
                fish_triggered = True
                print(f"[*] 命中关键词「鱼」概率唤醒触发: roll={roll:.3f} < {FISH_TRIGGER_PROBABILITY}")
            else:
                print(f"[-] 忽略「鱼」关键词: roll={roll:.3f} >= {FISH_TRIGGER_PROBABILITY} (静默不打扰)")

        if is_at or has_direct_keyword or fish_triggered:
            is_triggered = True

    if not is_triggered:
        return

    # 展开合并转发与引用
    extra_context_lines = []
    for fid in forward_ids:
        f_txt, f_imgs = await get_forward_content(ws, fid)
        if f_txt: extra_context_lines.append(f_txt)
        for u in f_imgs:
            if u not in image_urls: image_urls.append(u)

    for rid in reply_ids:
        r_txt, r_imgs = await get_msg_content(ws, rid)
        if r_txt: extra_context_lines.append(f"【引用的消息】: {r_txt}")
        for u in r_imgs:
            if u not in image_urls: image_urls.append(u)

    full_user_msg = "\n".join(extra_context_lines + ([user_text] if user_text else []))
    if not full_user_msg and not image_urls:
        full_user_msg = "在吗喵？"
    elif not full_user_msg and image_urls:
        full_user_msg = "（发了张图片/表情包）"

    # 上下文提取与模型会话
    if msg_type == "group":
        if GROUP_SESSION_MODE == "user":
            session_key = f"group_{group_id}_user_{user_id}"
        else:
            session_key = f"group_{group_id}"
        recent_ctx, context_images = await fetch_recent_group_context(
            ws, group_id, event.get("message_id"), limit=GROUP_CONTEXT_LIMIT
        )
        if not image_urls and context_images:
            print(f"[*] 当前消息无图，回溯补充群聊最近 {len(context_images)} 张表情包/图片供视觉分析")
            image_urls.extend(context_images)
    else:
        session_key = f"private_{user_id}"
        recent_ctx = ""

    print(f"[*] 正在生成回复: 来源={session_key}, 用户={sender}")
    reply, gen_img, gen_voice = await ask_llm(session_key, sender, full_user_msg, image_urls, recent_ctx)

    if reply or gen_img:
        clean_reply = clean_markdown_for_qq(reply) if reply else ""
        
        # 判定是否需要触发长回复折叠 (超过设定字符数或行数自动收起到合并转发一条聊天记录)
        is_long_reply = (
            FORWARD_FOLD_ENABLED and clean_reply and
            (len(clean_reply) >= FORWARD_FOLD_THRESHOLD or len(clean_reply.splitlines()) >= FORWARD_FOLD_LINES)
        )

        sent_via_forward = False
        if is_long_reply:
            print(f"[*] 检测到长文本回复 (长度: {len(clean_reply)} 字, {len(clean_reply.splitlines())} 行)，自动折叠打包为合并转发...")
            # 1. 先发送简短引用提示
            prompt_msg = []
            orig_msg_id = event.get("message_id")
            if orig_msg_id:
                prompt_msg.append({"type": "reply", "data": {"id": str(orig_msg_id)}})
            prompt_msg.append({"type": "text", "data": {"text": "内容放在下面的聊天记录里啦~ 🐾"}})
            
            prompt_payload = {
                "action": "send_group_msg" if msg_type == "group" else "send_private_msg",
                "params": {
                    ("group_id" if msg_type == "group" else "user_id"): (group_id if msg_type == "group" else user_id),
                    "message": prompt_msg
                }
            }
            await ws_send(ws, prompt_payload)

            # 2. 发送合并转发卡片节点
            node_content = [{"type": "text", "data": {"text": clean_reply}}]
            if gen_img:
                print(f"[+] 正在将生成的 SVG 渲染图片放入合并转发 (Base64 大小: {len(gen_img)})")
                node_content.append({"type": "image", "data": {"file": f"base64://{gen_img}"}})

            forward_nodes = [
                {
                    "type": "node",
                    "data": {
                        "name": "小橘",
                        "uin": str(BOT_QQ),
                        "content": node_content
                    }
                }
            ]
            fwd_action = "send_group_forward_msg" if msg_type == "group" else "send_private_forward_msg"
            fwd_params = {
                ("group_id" if msg_type == "group" else "user_id"): (group_id if msg_type == "group" else user_id),
                "messages": forward_nodes
            }
            # 超时设为 25.0 秒，给大体积图片和企鹅后台云同步留足充分时间
            fwd_resp = await call_api(ws, fwd_action, fwd_params, timeout=25.0)
            if fwd_resp and fwd_resp.get("status") == "ok":
                sent_via_forward = True
                print(f"[+] 合并转发长回复下发成功！")
            elif fwd_resp is None:
                # 核心防重复机制：若接口仅是等待回包超时，底层 OneBot 实际上已将长文本和图包排队上云并下发
                # 严禁再次回退发送全量原始文本，彻底杜绝聊天界面出现【合并转发 + 全量长文】的双重刷屏 Bug！
                print(f"[*] 合并转发已提交底层协议栈处理 (等待回包超时)，标记为已接管，避免重复吐字。")
                sent_via_forward = True
            else:
                print(f"[-] 合并转发接口明确返回失败 ({fwd_resp.get('message')})，回退直接消息发送")

        if not sent_via_forward:
            out_msg = []
            if clean_reply:
                out_msg.append({"type": "text", "data": {"text": clean_reply}})
            if gen_img:
                print(f"[+] 正在向 QQ 下发生成的 SVG 渲染图片 (Base64 大小: {len(gen_img)})")
                out_msg.append({"type": "image", "data": {"file": f"base64://{gen_img}"}})
            if msg_type == "group":
                payload = {
                    "action": "send_group_msg",
                    "params": {"group_id": group_id, "message": out_msg}
                }
            else:
                payload = {
                    "action": "send_private_msg",
                    "params": {"user_id": user_id, "message": out_msg}
                }
            await ws_send(ws, payload)

    if gen_voice:
        print(f"[+] 正在向 QQ 下发生成的 Despina 导演语音气泡 (Base64 大小: {len(gen_voice)})")
        voice_payload = {
            "action": "send_group_msg" if msg_type == "group" else "send_private_msg",
            "params": {
                ("group_id" if msg_type == "group" else "user_id"): (group_id if msg_type == "group" else user_id),
                "message": [{"type": "record", "data": {"file": f"base64://{gen_voice}"}}]
            }
        }
        await asyncio.sleep(0.3)
        await ws_send(ws, voice_payload)

async def process_notice_event(ws, event: Dict[str, Any]):
    """处理 OneBot notice 通知事件 (戳一戳/拍一拍)"""
    if event.get("sub_type") == "poke":
        target_id = event.get("target_id")
        user_id = event.get("user_id")
        if blacklist_manager.is_blocked(str(user_id)):
            return
        group_id = event.get("group_id")
        if str(target_id) == str(BOT_QQ) and str(user_id) != str(BOT_QQ):
            reactions = [
                "喵呜！谁在戳阿橘的肚皮！(爪子拍飞)",
                "呼噜噜...戳我干嘛喵？有小鱼干吃吗？",
                "（伸了个懒腰翻了个身）摸摸头可以，戳戳不行喵！",
                "甩甩尾巴啪叽拍在你的手上喵~ 别捣乱啦！"
            ]
            chosen = random.choice(reactions)
            if group_id:
                await ws_send(ws, {
                    "action": "send_group_msg",
                    "params": {
                        "group_id": group_id,
                        "message": [
                            {"type": "at", "data": {"qq": str(user_id)}},
                            {"type": "text", "data": {"text": " " + chosen}}
                        ]
                    }
                })
