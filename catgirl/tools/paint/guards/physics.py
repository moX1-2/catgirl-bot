# -*- coding: utf-8 -*-
"""
运动物理与道具常识守卫模块 (Physics Guard)
解决 AI 绘图在球类运动中容易出现的“一人一个球”、“场上多个排球/篮球”等低级道具克隆问题
"""

SPORTS_PHYSICS_GUARD = (
    "SPORTS PROPS & PHYSICAL LOGIC ANCHOR (STRICT COMPLIANCE): "
    "1. SINGLE BALL CONSTRAINTS: In any ball game or athletic sport scene (volleyball, basketball, soccer, tennis, beach volleyball), "
    "THERE MUST BE EXACTLY ONE SINGLE BALL IN THE ENTIRE SCENE (STRICTLY ONE BALL ONLY). "
    "FORBIDDEN: Absolutely NO duplicate balls, NO multiple volleyballs, NO extra balls floating near players! "
    "All players on court must interact with or focus their attention on the SAME SINGLE BALL in mid-air or mid-play. "
    "2. Dynamic Particle Physics: Realistic splashing sand, kicked-up dust, water droplets, and authentic kinetic momentum."
)

BALL_SPORTS_KEYWORDS = [
    "排球", "沙滩排球", "足球", "篮球", "网球", "羽毛球", "棒球", "乒乓球", "踢球", "发球", "扣杀", "垫球",
    "volleyball", "beach volleyball", "basketball", "soccer", "football", "tennis", "ball game"
]

def is_ball_sport(text: str) -> bool:
    """检测输入提示词是否涉及球类竞技或运动"""
    t = text.lower()
    return any(kw in t for kw in BALL_SPORTS_KEYWORDS)
