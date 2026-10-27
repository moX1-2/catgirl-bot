# -*- coding: utf-8 -*-
"""
速率限制器模块
包含 Tavily 搜索速率限制与陌生人私聊保护限制
"""

import time
from collections import defaultdict, deque
from .config import TAVILY_MAX_PER_MINUTE, TAVILY_MIN_INTERVAL, DM_LIMIT_PER_MINUTE

class TavilySearchRateLimiter:
    """搜索速率限制器：1 分钟最多 10 次，且保证最小间隔"""
    def __init__(self, max_per_minute=TAVILY_MAX_PER_MINUTE, min_interval=TAVILY_MIN_INTERVAL):
        self.max_per_minute = max_per_minute
        self.min_interval = min_interval
        self.timestamps = deque()
        self.last_search_time = 0.0

    def allow(self) -> tuple[bool, str]:
        now = time.time()
        while self.timestamps and self.timestamps[0] <= now - 60.0:
            self.timestamps.popleft()
        if len(self.timestamps) >= self.max_per_minute:
            return False, f"阿橘搜索太频繁啦喵（1分钟内已达 {self.max_per_minute} 次上限），稍等半分钟再试喵！"
        self.timestamps.append(now)
        self.last_search_time = now
        return True, ""

class DmRateLimiter:
    """私聊速率限制：非好友/陌生人限制每分钟最多 5 条消息"""
    def __init__(self, limit=DM_LIMIT_PER_MINUTE, window=60.0):
        self.limit = limit
        self.window = window
        self.records = defaultdict(deque)

    def check_and_record(self, user_id: str, is_friend: bool = False) -> tuple[bool, str]:
        if is_friend:
            return True, ""
        now = time.time()
        dq = self.records[str(user_id)]
        while dq and dq[0] <= now - self.window:
            dq.popleft()
        if len(dq) >= self.limit:
            return False, "喵呜...私聊太快啦！阿橘的脑袋要冒烟了喵，一分钟只能发 5 条消息哦，稍等一下再找我吧~"
        dq.append(now)
        return True, ""

# 模块单例
search_limiter = TavilySearchRateLimiter()
dm_limiter = DmRateLimiter()
