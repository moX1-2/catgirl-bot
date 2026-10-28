# -*- coding: utf-8 -*-
"""
OneBot 11 协议适配层
"""

from .client import (
    ws_send,
    call_api,
    ensure_friend_list_cached,
    cached_friend_ids,
    pending_requests
)
from .parser import (
    QQ_FACE_MAP,
    decode_qq_face,
    extract_clean_text,
    clean_markdown_for_qq,
    extract_text_from_segments,
    get_msg_content,
    get_forward_content
)
from .context import (
    group_recent_messages,
    record_recent_group_message,
    fetch_recent_group_context
)

__all__ = [
    "ws_send",
    "call_api",
    "ensure_friend_list_cached",
    "cached_friend_ids",
    "pending_requests",
    "QQ_FACE_MAP",
    "decode_qq_face",
    "extract_clean_text",
    "clean_markdown_for_qq",
    "extract_text_from_segments",
    "get_msg_content",
    "get_forward_content",
    "group_recent_messages",
    "record_recent_group_message",
    "fetch_recent_group_context"
]
