# -*- coding: utf-8 -*-
"""
会话历史管理器
负责会话 TTL 过期清理、滑动窗口截断与记忆管理
"""

import time
from typing import Dict, Any, List
from ..config import SESSION_EXPIRE_SECONDS, MAX_HISTORY_TURNS

# 全局对话历史字典
# key -> {"last_time": float, "messages": list}
chat_histories: Dict[str, Dict[str, Any]] = {}

def get_session_history(session_key: str) -> List[Dict[str, Any]]:
    """获取指定会话的历史消息列表，自动进行 TTL 检查与更新"""
    now = time.time()
    if session_key not in chat_histories or (now - chat_histories[session_key]["last_time"] > SESSION_EXPIRE_SECONDS):
        if session_key in chat_histories:
            try:
                from ..workspace import workspace_manager
                workspace_manager.cleanup_workspace(session_key)
            except Exception:
                pass
        chat_histories[session_key] = {"last_time": now, "messages": []}
    else:
        chat_histories[session_key]["last_time"] = now
    return chat_histories[session_key]["messages"]

def append_to_history(session_key: str, user_entry: str, assistant_entry: str):
    """记录一轮对话历史并自动裁剪"""
    now = time.time()
    if session_key not in chat_histories:
        chat_histories[session_key] = {"last_time": now, "messages": []}
    else:
        chat_histories[session_key]["last_time"] = now

    msgs = chat_histories[session_key]["messages"]
    msgs.append({"role": "user", "content": user_entry})
    msgs.append({"role": "assistant", "content": assistant_entry})

    # 保持最多 MAX_HISTORY_TURNS 轮
    if len(msgs) > MAX_HISTORY_TURNS * 2:
        chat_histories[session_key]["messages"] = msgs[-MAX_HISTORY_TURNS * 2:]

def clear_session_history(session_key: str):
    """清空指定会话的记忆，并全自动彻底释放其绑定的沙箱工作区与临时文件"""
    if session_key in chat_histories:
        chat_histories[session_key]["messages"] = []
    try:
        from ..workspace import workspace_manager
        workspace_manager.cleanup_workspace(session_key)
    except Exception:
        pass

def get_active_session_count() -> int:
    """返回当前未过期的活跃会话数"""
    now = time.time()
    return sum(1 for v in chat_histories.values() if now - v.get("last_time", 0) <= SESSION_EXPIRE_SECONDS)
