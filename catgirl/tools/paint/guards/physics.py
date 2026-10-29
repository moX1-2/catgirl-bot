# -*- coding: utf-8 -*-
"""
运动物理与道具常识守卫模块 (Physics Guard)
解决 AI 绘图在球类运动中容易出现的“一人一个球”、“场上多个排球/篮球”等低级道具克隆问题
"""

SPORTS_PHYSICS_GUARD = (
    "SPORTS PROPS & PHYSICAL LOGIC ANCHOR (STRICT SINGLE-MENTION RULE): "
    "1. STRICTLY ONE BALL ONLY: In any ball game or athletic sport (volleyball, basketball, soccer, tennis), "
    "THERE IS ONLY ONE SINGLE FLYING BALL IN THE ENTIRE COMPOSITION. "
    "NEVER create duplicate balls! Character slots must describe body motions only (e.g. forearms joined in bump stance, leaping arm swing), "
    "while the ball is declared strictly ONCE as a unique shared object suspended between players. "
    "2. Kinetic Momentum: Realistic sand splashing, dynamic speed blur, and water droplets."
)

BALL_SPORTS_KEYWORDS = [
    "排球", "沙滩排球", "足球", "篮球", "网球", "羽毛球", "棒球", "乒乓球", "踢球", "发球", "扣杀", "垫球",
    "volleyball", "beach volleyball", "basketball", "soccer", "football", "tennis", "ball game"
]

def is_ball_sport(text: str) -> bool:
    """检测输入提示词是否涉及球类竞技或运动"""
    t = text.lower()
    return any(kw in t for kw in BALL_SPORTS_KEYWORDS)
