# -*- coding: utf-8 -*-
"""
镜头视角与动态姿态导演模块 (Camera & Pose Director)
提供电影级运镜透视与动作抽样，杜绝死板证件照与僵硬站桩
"""

import random

# 动态姿态大辞典
DYNAMIC_POSES = {
    "cute_casual": [
        "leaning forward playfully with one hand reaching out toward viewer with open palm, gentle head tilt, dynamic foreshortening, intimate connection",
        "sitting comfortably on a scenic balustrade or stone ledge, dangling legs with one knee raised, relaxed natural posture, tilting head upward to the sky",
        "playful cute gesture with one hand making a soft cat paw or gentle peace sign near cheek, slight playful wink, expressive radiant face",
        "holding a small delicious pastry or sweet drink with both hands, taking a tiny cute bite with softly blushing cheeks, charming candid moment",
        "gentle morning stretch with arms raised overhead, arching back slightly, soft warm smile, casual cozy atmosphere",
        "resting chin in hands while leaning across a wooden tabletop, looking up with curious twinkling eyes and soft smile",
        "holding a fluffy cat or mascot plushie close to chest, nuzzling face into it with a sweet contented grin",
        "tucking a soft stray strand of hair behind ear, looking directly into camera with shy blushing smile, intimate framing"
    ],
    "dynamic_action": [
        "dynamic combat action stance with glowing energy particles swirling around hands, dramatic low angle shot, hair billowing with motion blur",
        "turning back mid-motion to look over shoulder with a radiant determined expression, running turn, dynamic hair and skirt fluttering in the wind",
        "drawing sword from scabbard with crisp diagonal motion, blade catching a brilliant gleam of light, sharp focused gaze",
        "mid-air acrobatic leap, one leg extended and ribbons spiraling outward, dynamic diagonal camera framing",
        "landing from a jump with one hand touching the ground, shockwave energy ripples expanding beneath feet, dramatic foreshortening",
        "casting an intricate glowing magic circle in front of hands, concentrated magic glow illuminating face in sharp contrast",
        "diving forward for an athletic save or spike, sand splashing, energetic kinetic action"
    ],
    "dreamy_poetic": [
        "floating weightlessly in mid-air in zero gravity, legs slightly curved in elegant flow, floating ribbons and hair strands, ethereal dreamscape",
        "gently holding a glowing star lantern, lightly lifting dress hem with one hand while turning along a petal-strewn path",
        "leaning against a rustic balcony railing at dusk, breeze gently parting hair, thoughtful melancholic yet warm gaze toward horizon",
        "walking slowly barefoot along the water's edge, dress gently skimming reflective shallow water, glowing ripples expanding outward",
        "holding hands close to heart with fingers intertwined, eyes gently closed in quiet wish or prayer, serene glowing particles"
    ]
}

# 镜头构图与透视库
CAMERA_PERSPECTIVES = [
    "cinematic low angle perspective with dynamic diagonal framing and sense of scale",
    "slight high angle looking down with dramatic depth of field and soft circular bokeh",
    "dutch angle dynamic composition with foreground light elements",
    "cinematic wide three-quarter view with foreground light leaks and rim light",
    "intimate close-up portrait with shallow depth of field and glowing eye reflections",
    "wide environmental shot balancing the character silhouette with breathtaking panoramic scenery"
]

CUSTOM_POSE_KEYWORDS = [
    "坐", "躺", "跑", "战", "飞", "吃", "拿", "看", "笑", "站", "握", "跃", "挥", "扣", "垫", "扑",
    "pose", "stand", "sit", "run", "jump", "eating", "fighting", "diving"
]

def pick_camera_and_pose(prompt: str) -> str:
    """按需为未指定姿态的提示词装配动态动作与镜头透视"""
    p_lower = prompt.lower()
    has_custom = any(kw in p_lower for kw in CUSTOM_POSE_KEYWORDS)

    parts = []
    if not has_custom:
        has_action = any(kw in p_lower for kw in ["战", "打", "剑", "刀", "魔", "排球", "跑", "fight", "sword", "action"])
        has_dreamy = any(kw in p_lower for kw in ["星", "梦", "海", "空", "月", "花", "dream", "star", "space", "moon"])
        if has_action:
            parts.append(random.choice(DYNAMIC_POSES["dynamic_action"]))
        elif has_dreamy:
            parts.append(random.choice(DYNAMIC_POSES["dreamy_poetic"]))
        else:
            parts.append(random.choice(DYNAMIC_POSES["cute_casual"]))

    parts.append(random.choice(CAMERA_PERSPECTIVES))
    return ", ".join(parts)
