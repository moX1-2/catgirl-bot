# -*- coding: utf-8 -*-
"""
小橘 Agent QQ Bot 服务主入口
"""

import json
import asyncio
import websockets
from .config import (
    BOT_QQ,
    ONEBOT_WS_URI,
    ENABLE_HEARTBEAT,
    HEARTBEAT_INTERVAL
)
from .onebot.client import ws_send, pending_requests
from .handlers.dispatcher import process_message_event, process_notice_event

async def ws_receiver(ws, event_queue: asyncio.Queue):
    """WebSocket 接收协程，将 OneBot 事件路由到工作队列"""
    try:
        async for message in ws:
            try:
                data = json.loads(message)
                if "echo" in data:
                    echo_id = data["echo"]
                    if echo_id in pending_requests:
                        await pending_requests[echo_id].put(data)
                elif data.get("post_type") in ["message", "notice"]:
                    await event_queue.put(data)
            except Exception as e:
                print(f"[-] 解析事件异常: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass

async def event_worker(ws, event_queue: asyncio.Queue):
    """事件处理工作协程，异步派发各类型事件"""
    while True:
        event = await event_queue.get()
        pt = event.get("post_type")
        if pt == "message":
            asyncio.create_task(process_message_event(ws, event))
        elif pt == "notice":
            asyncio.create_task(process_notice_event(ws, event))
        event_queue.task_done()

async def heartbeat_worker(ws):
    """定时保活协程"""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        try:
            payload = {
                "action": "send_private_msg",
                "params": {"user_id": int(BOT_QQ), "message": "[心跳保活] 阿橘正在深海/阳台晒太阳，一切正常喵~"}
            }
            await ws_send(ws, payload)
        except Exception as e:
            print(f"[-] 发送心跳异常: {e}")

async def main():
    """主调度循环，具备网络异常自动重连机制"""
    print(f"[*] 正在启动 DSH 自主 Agent QQ Bot (账号: {BOT_QQ})...")
    while True:
        try:
            async with websockets.connect(ONEBOT_WS_URI, ping_interval=20, ping_timeout=10) as ws:
                print(f"[+] 成功连接 NapCat OneBot (ws://127.0.0.1:3001)！")
                print(f"[+] DSH 模块化架构已加载 (UTC+8墙钟 / Tavily多Key搜索 / 私聊限速 / 戳一戳互动 / 10轮自反思视觉)")
                event_queue = asyncio.Queue()
                receiver_task = asyncio.create_task(ws_receiver(ws, event_queue))
                worker_task = asyncio.create_task(event_worker(ws, event_queue))
                tasks_to_wait = [receiver_task, worker_task]
                if ENABLE_HEARTBEAT:
                    tasks_to_wait.append(asyncio.create_task(heartbeat_worker(ws)))
                await asyncio.wait(tasks_to_wait, return_when=asyncio.FIRST_COMPLETED)
                for t in tasks_to_wait:
                    t.cancel()
        except Exception as e:
            print(f"[-] 连接断开或重试中: {e}，5秒后自动重连...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[*] 机器人已手动停止。")
