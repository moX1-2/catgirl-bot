# -*- coding: utf-8 -*-
"""
解剖结构与多人互动安全守卫模块 (Anatomy Guard)
解决 AI 绘图的多人肢体粘连、三只手、多余手指、五官融化等经典解剖硬伤
"""

import re

MULTI_PERSON_ANATOMY_GUARD = (
    "ANATOMICAL & MULTI-CHARACTER STRUCTURAL ANCHOR (STRICT COMPLIANCE): "
    "1. Distinct Character Separation: Keep individual character silhouettes and outlines completely separate. "
    "2. Arm and Hand Integrity: Each character has strictly two arms, two hands, and exactly five fingers per hand. "
    "STRICTLY FORBIDDEN: NO extra hands, NO three hands, NO floating detached limbs, NO fused bodies, NO mutated or conjoined fingers. "
    "3. Intimate Pose Geometry (Kissing/Embracing): MUST use side profile view or clean three-quarter profile shot. "
    "Ensure clear facial boundary contours with natural head tilts; lips touch delicately without facial melting, smashing, or blurred overlapping. "
    "Hand placement must be anatomically logical (e.g. naturally resting on shoulder, waist, or gently cradling cheek)."
)

MULTI_PERSON_KEYWORDS = [
    "亲吻", "吻", "拥抱", "抱", "贴贴", "和", "与", "俩", "两人", "双人", "两只", "三位", "三人", "群像", "并肩", "对决",
    "kiss", "hug", "together", "each other", "two girls", "couple", "yuri", "yaoi", "embrace", "holding hands"
]

def is_multi_character(text: str) -> bool:
    """检测输入提示词是否涉及多人或亲密互动"""
    t = text.lower()
    return any(kw in t for kw in MULTI_PERSON_KEYWORDS)
