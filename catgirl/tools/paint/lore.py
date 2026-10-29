# -*- coding: utf-8 -*-
"""
参考图与世界观特征对齐模块 (Lore & Reference Isolator)
严格隔离参考图背景，仅继承角色外观特征，严防场景污染
"""

def build_multimodal_reference_payload(
    clean_prompt: str,
    reference_url: str,
    dynamic_modifiers: str,
    booster: str
) -> list:
    """
    组装严格隔离背景的多模态图生图 Payload
    把用户指令置于不可撼动的最高优先级，明确禁止抄袭参考图背景
    """
    ref_u = reference_url.strip()
    instruction_text = (
        f"USER'S MANDATORY CORE INSTRUCTION (HIGHEST PRIORITY): {clean_prompt}\n\n"
        f"REFERENCE IMAGE GUIDANCE: Use the provided reference image EXCLUSIVELY to recognize the character's face, hair color/style, eye color, and character design. "
        f"CRITICAL OVERRIDE: DO NOT COPY THE BACKGROUND, SCENE, OR SURROUNDING ENVIRONMENT FROM THE REFERENCE IMAGE! "
        f"You MUST place the characters into the EXACT setting and action demanded by the user above (Setting & Action: {clean_prompt}).\n"
        f"Composition & Dynamic Style: {booster}. Additional details: {dynamic_modifiers}"
    )

    return [
        {"type": "text", "text": instruction_text},
        {"type": "image_url", "image_url": {"url": ref_u}}
    ]
