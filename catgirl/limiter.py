# -*- coding: utf-8 -*-
"""
速率限制器与黑名单管理模块
包含 Tavily 搜索速率限制、陌生人私聊保护限制以及防 Bot 回声/死循环的持久化黑名单
"""

import os
import json
import time
from collections import defaultdict, deque
from typing import Set, List
from .config import TAVILY_MAX_PER_MINUTE, TAVILY_MIN_INTERVAL, DM_LIMIT_PER_MINUTE, IMAGE_GEN_MAX_PER_MINUTE

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


class ImageGenerationRateLimiter:
    """绘画速率限制器：滑动窗口限制 1 分钟最多生成 8 张图片 (支持每次双候选并发及自检重绘)"""
    def __init__(self, max_per_minute=IMAGE_GEN_MAX_PER_MINUTE):
        self.max_per_minute = max_per_minute
        self.timestamps = deque()

    def allow(self, count: int = 1) -> tuple[bool, str]:
        now = time.time()
        while self.timestamps and self.timestamps[0] <= now - 60.0:
            self.timestamps.popleft()
        if len(self.timestamps) + count > self.max_per_minute:
            wait_sec = int(60.0 - (now - self.timestamps[0])) + 1 if self.timestamps else 15
            return False, f"阿橘画画爪子要冒烟啦喵（绘图限制 1 分钟最多 {self.max_per_minute} 张，当前剩余额度不足 {count} 张），还需冷却 {wait_sec} 秒喵！"
        for _ in range(count):
            self.timestamps.append(now)
        return True, ""

class BlacklistManager:
    """持久化黑名单管理器，防止恶意刷屏与 Bot 间互相对话/回声死循环"""
    def __init__(self, file_path=None):
        if file_path is None:
            file_path = os.getenv("BLACKLIST_FILE", os.path.join(os.path.dirname(__file__), "blacklist.json"))
        self.file_path = file_path
        self.blocked_users: Set[str] = set()
        self.load()

    def load(self):
        if os.path.isfile(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.blocked_users = set(str(x).strip() for x in data if str(x).strip())
            except Exception as e:
                print(f"[-] 读取黑名单文件失败: {e}")

    def save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(sorted(list(self.blocked_users)), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[-] 保存黑名单文件失败: {e}")

    def is_blocked(self, user_id: str) -> bool:
        return str(user_id).strip() in self.blocked_users

    def block(self, user_id: str) -> bool:
        u = str(user_id).strip()
        if not u:
            return False
        if u not in self.blocked_users:
            self.blocked_users.add(u)
            self.save()
            return True
        return False

    def unblock(self, user_id: str) -> bool:
        u = str(user_id).strip()
        if u in self.blocked_users:
            self.blocked_users.remove(u)
            self.save()
            return True
        return False

    def list_all(self) -> List[str]:
        return sorted(list(self.blocked_users))

# 模块单例
search_limiter = TavilySearchRateLimiter()
dm_limiter = DmRateLimiter()
blacklist_manager = BlacklistManager()
image_limiter = ImageGenerationRateLimiter()
