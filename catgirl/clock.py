# -*- coding: utf-8 -*-
"""
UTC+8 墙钟服务
提供精准的北京时间、星期与时段计算
"""

from datetime import datetime, timezone, timedelta

def get_utc8_wall_clock() -> str:
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday_str = weekdays[now.weekday()]
    h = now.hour
    if 5 <= h < 9: period = "清晨"
    elif 9 <= h < 12: period = "上午"
    elif 12 <= h < 14: period = "中午"
    elif 14 <= h < 18: period = "下午"
    elif 18 <= h < 23: period = "晚上"
    else: period = "深夜"
    return f"【当前真实时间 (UTC+8)】: {now.strftime('%Y-%m-%d %H:%M:%S')} {weekday_str}（{period}）"
