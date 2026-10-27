# -*- coding: utf-8 -*-
"""
OneBot 11 协议客户端与异步 RPC 封装
"""

import json
import uuid
import time
import asyncio
from typing import Dict, Any, Optional, Set

ws_send_lock = asyncio.Lock()
pending_requests: Dict[str, asyncio.Queue] = {}
cached_friend_ids: Set[str] = set()
last_friend_refresh = 0.0

async def ws_send(ws, payload: dict):
    """加锁向 OneBot WebSocket 发送消息，避免并发冲突"""
    async with ws_send_lock:
        await ws.send(json.dumps(payload))

async def call_api(ws, action: str, params: dict, timeout: float = 8.0) -> Optional[dict]:
    """发起 OneBot RPC 异步请求并等待 echo 响应返回"""
    echo = f"{action}_{uuid.uuid4().hex[:8]}"
    queue = asyncio.Queue()
    pending_requests[echo] = queue
    payload = {"action": action, "params": params, "echo": echo}
    try:
        await ws_send(ws, payload)
        response = await asyncio.wait_for(queue.get(), timeout=timeout)
        return response
    except asyncio.TimeoutError:
        print(f"[API超时] {action}: params={params}")
        return None
    except Exception as e:
        print(f"[API异常] {action}: {e}")
        return None
    finally:
        pending_requests.pop(echo, None)

async def ensure_friend_list_cached(ws):
    """定时同步并缓存机器人好友列表 (用于陌生人限流校验)"""
    global cached_friend_ids, last_friend_refresh
    now = time.time()
    if now - last_friend_refresh > 300:
        try:
            res = await call_api(ws, "get_friend_list", {})
            if res and isinstance(res.get("data"), list):
                cached_friend_ids = {str(item.get("user_id")) for item in res["data"] if item.get("user_id")}
                last_friend_refresh = now
                print(f"[+] 好友列表已同步: 共 {len(cached_friend_ids)} 位好友")
        except Exception as e:
            print(f"[-] 获取好友列表异常: {e}")
