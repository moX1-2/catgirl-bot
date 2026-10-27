# -*- coding: utf-8 -*-
"""
小橘 Agent 决策核心
"""

from .client import get_llm_client
from .history import (
    chat_histories,
    get_session_history,
    append_to_history,
    clear_session_history,
    get_active_session_count
)
from .loop import ask_llm

__all__ = [
    "get_llm_client",
    "chat_histories",
    "get_session_history",
    "append_to_history",
    "clear_session_history",
    "get_active_session_count",
    "ask_llm"
]
