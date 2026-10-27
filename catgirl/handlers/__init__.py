# -*- coding: utf-8 -*-
"""
业务事件派发与指令处理器
"""

from .admin import build_help_message, get_system_status_text, handle_admin_or_help
from .dispatcher import process_message_event, process_notice_event

__all__ = [
    "build_help_message",
    "get_system_status_text",
    "handle_admin_or_help",
    "process_message_event",
    "process_notice_event"
]
