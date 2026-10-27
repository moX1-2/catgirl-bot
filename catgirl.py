# -*- coding: utf-8 -*-
"""
DSH 自主 Agent QQ Bot 启动入口
"""
import asyncio
from catgirl.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[*] 机器人已手动停止。")
