# -*- coding: utf-8 -*-
"""
智能绘图提示词动态装配器 (Prompt Composer)
基于用户输入语义，按需动态加载解剖守卫、运动物理守卫、镜头姿态与环境氛围
彻底解耦巨石提示词，实现上下文自适应装配
"""

from typing import Union, List, Dict
from .guards import (
    MULTI_PERSON_ANATOMY_GUARD,
    is_multi_character,
    SPORTS_PHYSICS_GUARD,
    is_ball_sport,
    pick_camera_and_pose,
    pick_atmosphere,
    MASTERPIECE_BOOSTER
)
from .lore import build_multimodal_reference_payload

def compose_generation_payload(
    clean_prompt: str,
    reference_image_url: str = None
) -> Union[str, List[Dict[str, str]]]:
    """
    按需动态装配生图 Payload：
    1. 嗅探是否为多人互动 -> 按需装配解剖守卫 (防三只手/五官融化)
    2. 嗅探是否为球类运动 -> 按需装配物理守卫 (全场单球/防道具克隆)
    3. 嗅探是否缺少动作 -> 动态抽样姿态与电影构图
    4. 嗅探是否缺少环境 -> 补充电影级氛围场景
    5. 若有参考图 -> 强制执行背景隔离与用户设定置顶
    """
    modifiers = []

    # 1. 守卫按需注入 (Contextual Guard Injection)
    if is_multi_character(clean_prompt):
        modifiers.append(MULTI_PERSON_ANATOMY_GUARD)

    if is_ball_sport(clean_prompt):
        modifiers.append(SPORTS_PHYSICS_GUARD)

    # 2. 镜头与姿态
    camera_and_pose = pick_camera_and_pose(clean_prompt)
    if camera_and_pose:
        modifiers.append(camera_and_pose)

    # 3. 场景氛围
    atmosphere = pick_atmosphere(clean_prompt)
    if atmosphere:
        modifiers.append(atmosphere)

    dynamic_details = "; ".join(modifiers)

    # 4. 参考图图生图 vs 纯文生图
    if reference_image_url and reference_image_url.strip().startswith("http"):
        return build_multimodal_reference_payload(
            clean_prompt=clean_prompt,
            reference_url=reference_image_url.strip(),
            dynamic_modifiers=dynamic_details,
            booster=MASTERPIECE_BOOSTER
        )
    else:
        full_text = (
            f"USER'S MANDATORY CORE INSTRUCTION: {clean_prompt}\n\n"
            f"High quality anime masterpiece with dynamic pose and expressive lighting: "
            f"{MASTERPIECE_BOOSTER}. Detailed composition: {dynamic_details}"
        )
        return full_text
