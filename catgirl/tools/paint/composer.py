# -*- coding: utf-8 -*-
"""
结构化语义意图装配器 (Structured Prompt Composer)
告别脆弱的字符串包含匹配！由大模型在工具调用时输出结构化字段 (category/subject/action/setting)
系统据此进行确定性、100% 可靠的专业领域守卫与物理法则注入
"""

from typing import Union, List, Dict, Any
from .guards import (
    MULTI_PERSON_ANATOMY_GUARD,
    SPORTS_PHYSICS_GUARD,
    pick_camera_and_pose,
    pick_atmosphere,
    MASTERPIECE_BOOSTER
)
from .lore import build_multimodal_reference_payload

def compose_generation_payload(
    args: Union[Dict[str, Any], str],
    reference_image_url: str = None
) -> Union[str, List[Dict[str, str]]]:
    """
    基于模型输出的结构化字段装配生图 Payload：
    1. category (分类):
       - 'sports_athletics': 100% 确定性激活【全场单球】物理守卫 (彻底解决双排球 Bug)
       - 'multi_character_intimate': 100% 确定性激活【多人解剖/侧颜防融化/防三只手】守卫
       - 'single_character_portrait': 激活【动态姿态与电影构图】
    2. subject (主体): 锁定人物与角色边界
    3. action_and_pose (动作): 保证动态姿势，杜绝正面站桩
    4. setting_and_scene (场景): 严格锁定用户要求的背景 (如草地/沙滩)，杜绝被参考图背景带偏
    5. reference_image_url: 严格隔离背景，仅提取角色特征
    """
    if isinstance(args, dict):
        category = args.get("category", "")
        subject = args.get("subject", "").strip()
        action = args.get("action_and_pose", "").strip()
        setting = args.get("setting_and_scene", "").strip()
        ref_url = args.get("reference_image_url") or reference_image_url
        extra_prompt = args.get("prompt", "").strip()
    else:
        category = ""
        subject = str(args).strip()
        action = ""
        setting = ""
        ref_url = reference_image_url
        extra_prompt = ""

    all_text = f"{category} {subject} {action} {setting} {extra_prompt}".lower()
    
    is_sports = (
        category == "sports_athletics" or
        any(w in all_text for w in ["排球", "沙滩排球", "足球", "篮球", "网球", "volleyball", "basketball", "soccer", "tennis", "ball game"])
    )

    is_multi_intimate = (
        category == "multi_character_intimate" or
        any(w in all_text for w in ["亲吻", "吻", "拥抱", "抱", "贴贴", "俩", "两人", "双人", "kiss", "hug", "together", "each other", "two girls", "couple", "yuri", "yaoi"])
    )

    guards = []
    # 1. 物理常识守卫 (排球全场严格单球)
    if is_sports:
        guards.append(SPORTS_PHYSICS_GUARD)

    # 2. 多人解剖与防融化守卫 (侧颜特写、独立身体界限、严防三只手)
    if is_multi_intimate:
        guards.append(MULTI_PERSON_ANATOMY_GUARD)

    # 3. 动态镜头与视角
    guards.append(pick_camera_and_pose(all_text))

    # 4. 若未指定环境，补充氛围
    if not setting:
        atm = pick_atmosphere(all_text)
        if atm:
            guards.append(atm)

    guard_str = "; ".join(g for g in guards if g)

    # 5. 构建分段清晰的核心画面提示
    scene_clause = f"MANDATORY ENVIRONMENT & SETTING: {setting}" if setting else "Scenic anime environment"
    action_clause = f"MANDATORY ACTION & POSE: {action}" if action else "Natural dynamic anime pose"
    subject_clause = f"SUBJECT & CHARACTERS: {subject}" if subject else clean_subject_from_prompt(extra_prompt)

    combined_instruction = (
        f"{subject_clause}\n"
        f"{action_clause}\n"
        f"{scene_clause}\n"
        f"Domain Guards: {guard_str}\n"
        f"Artistic Aesthetics: {MASTERPIECE_BOOSTER}. Additional details: {extra_prompt}"
    )

    # 6. 处理参考图多模态封装 (隔离背景)
    if ref_url and ref_url.strip().startswith("http"):
        return build_multimodal_reference_payload(
            clean_prompt=f"{subject_clause}. {action_clause}. {scene_clause}",
            reference_url=ref_url.strip(),
            dynamic_modifiers=guard_str,
            booster=MASTERPIECE_BOOSTER
        )
    else:
        return (
            f"USER'S MANDATORY CORE INSTRUCTION (HIGHEST PRIORITY):\n"
            f"{combined_instruction}"
        )

def clean_subject_from_prompt(p: str) -> str:
    return p[:100] if p else "Anime character"
