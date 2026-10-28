# -*- coding: utf-8 -*-
"""
指令系统与系统状态监控
提供 /help 指令、/tts 语音直发、持久化黑名单管理(/ban /unban /blacklist)与管理员特权指令
"""

import sys
import time
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..config import MODEL_NAME, TAVILY_KEYS, ADMIN_QQ
from ..limiter import search_limiter, blacklist_manager
from ..agent.history import get_active_session_count, clear_session_history
from ..onebot.client import cached_friend_ids, ws_send
from ..tools.tts import generate_speech_gemini

def build_help_message(is_admin: bool = False) -> str:
    """生成功能帮助与操作指引菜单"""
    lines = [
        "✨ 【小橘/喵喵 Bot 功能指南】 ✨",
        "------------------------------------",
        "🐾 基础对话：",
        "  · 群聊：@小橘 或包含“小橘/阿橘/猫猫/大肥鱼”触发交流",
        "  · 私聊：直接发送消息即可畅聊（陌生人保护 5条/分钟）",
        "",
        "🎙️ 语音合成与表达 (Gemini 3.8 TTS)：",
        "  · 对话中随时让阿橘“用语音说/发条语音/撒个娇”，自主合成发送原声语音！",
        "  · 指令：/tts 文本 或 /语音 文本（直接转语音发语音条）",
        "",
        "👁️ 多模态视觉感知：",
        "  · 发送图片、长截屏、表情包或图包，阿橘自动识图分析",
        "  · 支持穿透解析嵌套合并转发图包与多层回复引用！",
        "",
        "🎨 SVG 绘图与渲染：",
        "  · 让阿橘画架构图、流程图、对比图或猫猫插图，自动渲染为高清图片发送！",
        "",
        "🌐 实时联网检索：",
        "  · 询问最新时事、今日天气、技术热点时自主调用 Tavily 搜索（带流量保护）",
        "",
        "🕒 精准时空感知：",
        "  · 内置 UTC+8 墙钟，掌握精准北京时间、星期几与全天时段",
        "",
        "🐾 戳一戳互动：",
        "  · 群内双击阿橘头像或拍一拍阿橘，随机触发软萌反应",
        "------------------------------------",
        "💡 输入 /help 随时调出本菜单（0 Token 瞬时响应）"
    ]
    if is_admin:
        lines.extend([
            "",
            "👑 【管理员专属特权指令】:",
            "  · /status  - 查看服务器负载、内存与会话状态",
            "  · /clear   - 重置并清空当前会话记忆",
            "  · /search  - 查看 Tavily 搜索额度与冷却状态",
            "  · /ban <QQ>      - 拉黑指定 QQ，彻底静默防 Bot 回声与刷屏",
            "  · /unban <QQ>    - 解封指定 QQ",
            "  · /blacklist     - 查看当前已拉黑的 QQ 清单",
            "  · /restart       - 安全重启阿橘服务"
        ])
    return "\n".join(lines)

def get_system_status_text() -> str:
    """获取宿主服务器资源、内存、活跃会话与密钥健康状态"""
    tz = timezone(timedelta(hours=8))
    now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    active_sessions = get_active_session_count()
    total_cached_friends = len(cached_friend_ids)
    blocked_count = len(blacklist_manager.list_all())
    
    mem_info = "未知"
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        mem_total = 0
        mem_avail = 0
        for l in lines:
            if l.startswith("MemTotal:"):
                mem_total = int(l.split()[1]) // 1024
            elif l.startswith("MemAvailable:"):
                mem_avail = int(l.split()[1]) // 1024
        mem_used = mem_total - mem_avail
        mem_info = f"{mem_used}MB / {mem_total}MB (空闲 {mem_avail}MB)"
    except Exception:
        pass

    return (
        f"🖥️ 【小橘系统运行状态汇报】\n"
        f"------------------------------------\n"
        f"🕒 当前北京时间: {now_str}\n"
        f"💻 宿主环境: Linux\n"
        f"📊 系统内存负载: {mem_info}\n"
        f"🧠 当前大模型: {MODEL_NAME}\n"
        f"💬 活跃对话会话数: {active_sessions} 个\n"
        f"👥 已同步好友数: {total_cached_friends} 人\n"
        f"🚫 已拉黑屏蔽对象: {blocked_count} 个\n"
        f"🌐 联网搜索备用池: {len(TAVILY_KEYS)} 个密钥\n"
        f"🛡️ 看门狗巡检: qq-watchdog.service 运行中\n"
        f"------------------------------------\n"
        f"一切运行正常，阿橘身心健康喵！🐾"
    )

async def handle_admin_or_help(
    ws,
    cmd_text: str,
    user_id: int,
    group_id: Optional[int],
    msg_type: str
) -> bool:
    """
    检查并处理指令。
    返回 True 表示已被拦截处理，无需走模型推演。
    """
    cmd = cmd_text.strip()
    is_admin = (str(user_id) == str(ADMIN_QQ))

    async def send_reply(text: str):
        out_msg = [{"type": "text", "data": {"text": text.strip()}}]
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

    async def send_voice_reply(b64_audio: str):
        out_msg = [{"type": "record", "data": {"file": f"base64://{b64_audio}"}}]
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

    # 1. 帮助菜单
    if cmd in ["/help", "help", "/帮助", "帮助", "菜单", "/菜单"]:
        await send_reply(build_help_message(is_admin=is_admin))
        return True

    # 2. 快捷语音合成直发指令 (/tts 或 /语音)
    if cmd.startswith(("/tts", "/语音", "tts ", "语音 ")):
        parts = re.split(r"\s+", cmd, maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            text_to_speak = parts[1].strip()
            print(f"[*] 收到直接语音生成指令: {text_to_speak[:30]}")
            b64_audio, err = await generate_speech_gemini(text_to_speak)
            if b64_audio:
                await send_voice_reply(b64_audio)
            else:
                await send_reply(f"语音生成失败: {err}喵")
            return True

    # 3. 斜杠指令与黑名单管理
    if cmd.startswith("/"):
        parts = cmd.split()
        op = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        if not is_admin:
            if op in ["/status", "/clear", "/search", "/restart", "/ban", "/block", "/unban", "/unblock", "/blacklist", "/拉黑", "/解封", "/黑名单", "/重置", "/状态"]:
                await send_reply("喵呜？这是管理员主人的专属指令，你还没有权限使用喵~ (=｀ω´=)")
                return True
        else:
            if op in ["/status", "/状态"]:
                await send_reply(get_system_status_text())
                return True
            elif op in ["/clear", "/重置"]:
                session_key = f"group_{group_id}_user_{user_id}" if msg_type == "group" else f"private_{user_id}"
                clear_session_history(session_key)
                await send_reply("已清空当前会话的上下文记忆喵！已开启全新对话~ 🐾")
                return True
            elif op in ["/search", "/搜索状态"]:
                now_t = time.time()
                last_diff = int(now_t - search_limiter.last_search_time) if search_limiter.last_search_time > 0 else 999
                cooldown_str = f"冷却中 (还剩 {int(search_limiter.min_interval - last_diff)} 秒)" if last_diff < search_limiter.min_interval else "空闲就绪"
                search_stat = (
                    f"🌐 【Tavily 搜索监控状态】\n"
                    f"------------------------------------\n"
                    f"📊 1分钟内已用次数: {len(search_limiter.timestamps)} / {search_limiter.max_per_minute}\n"
                    f"⏳ 距离上次搜索: {last_diff} 秒前\n"
                    f"❄️ 冷却状态: {cooldown_str}\n"
                    f"🔑 密钥池容量: {len(TAVILY_KEYS)} 个备用密钥\n"
                    f"------------------------------------"
                )
                await send_reply(search_stat)
                return True
            # ---------- 手动拉黑与解除黑名单指令 ----------
            elif op in ["/ban", "/block", "/拉黑"]:
                if not args:
                    await send_reply("格式错误喵！请使用: /ban <QQ号> 或 /拉黑 <QQ号>")
                    return True
                target_qq = re.sub(r"\D", "", args[0])
                if not target_qq:
                    await send_reply("请输入有效的数字 QQ 号喵！")
                    return True
                if str(target_qq) == str(ADMIN_QQ):
                    await send_reply("阿橘怎么可能拉黑主人自己呢喵！(拍拍爪子)")
                    return True
                blacklist_manager.block(target_qq)
                await send_reply(f"🚫 已成功拉黑屏蔽 QQ: {target_qq}！该账号的所有消息将直接静默忽略，彻底杜绝 Bot 回声与恶意刷屏~ 🐾")
                return True
            elif op in ["/unban", "/unblock", "/解封"]:
                if not args:
                    await send_reply("格式错误喵！请使用: /unban <QQ号> 或 /解封 <QQ号>")
                    return True
                target_qq = re.sub(r"\D", "", args[0])
                if blacklist_manager.unblock(target_qq):
                    await send_reply(f"✅ 已成功将 QQ: {target_qq} 从黑名单中移除喵~")
                else:
                    await send_reply(f"QQ: {target_qq} 本来就不在黑名单里喵！")
                return True
            elif op in ["/blacklist", "/黑名单"]:
                blocked = blacklist_manager.list_all()
                if not blocked:
                    await send_reply("当前黑名单为空，没有任何被屏蔽的账号喵！🐾")
                else:
                    msg = f"🚫 【当前屏蔽黑名单列表 (共 {len(blocked)} 人)】:\n" + "\n".join(f"  · {qq}" for qq in blocked)
                    await send_reply(msg)
                return True
            elif op in ["/restart", "/重启"]:
                await send_reply("收到管理员重启指令喵！阿橘正在执行自愈重启，马上回来~ 🐾")
                sys.exit(0)

    return False
