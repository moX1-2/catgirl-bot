import html
# -*- coding: utf-8 -*-
"""
Agent 决策主循环
包含多模态视觉处理、多轮自反思工具调用、SVG 视觉回显与优雅错误自愈兜底
"""

import re
import json
import asyncio
from typing import Optional, List, Tuple

from ..config import (
    MODEL_NAME,
    MAX_IMAGES_PER_TURN,
    MAX_HISTORY_TURNS,
)
from ..prompts import PROMPT_CATGIRL_BASE
from ..clock import get_utc8_wall_clock
from .client import get_llm_client
from .history import get_session_history, append_to_history
from ..tools.definitions import (
    TAVILY_TOOL_DEFINITION,
    DRAW_SVG_TOOL_DEFINITION,
    GENERATE_IMAGE_TOOL_DEFINITION,
    SEND_VOICE_TOOL_DEFINITION,
    WORKSPACE_RUN_TOOL_DEFINITION,
    WORKSPACE_WRITE_TOOL_DEFINITION,
    WORKSPACE_READ_TOOL_DEFINITION,
    WORKSPACE_LIST_TOOL_DEFINITION,
    FETCH_WEB_PAGE_TOOL_DEFINITION
)
from ..tools.tavily import perform_tavily_search
from ..tools.svg import render_svg_to_png_base64
from ..tools.tts import generate_speech
from ..tools.paint import generate_picture_gemini
from ..tools.fetch import fetch_web_page_content
from ..workspace import workspace_manager
from ..tools.image import fetch_image_as_base64


ALL_AGENT_TOOLS = [
    TAVILY_TOOL_DEFINITION,
    FETCH_WEB_PAGE_TOOL_DEFINITION,
    DRAW_SVG_TOOL_DEFINITION,
    GENERATE_IMAGE_TOOL_DEFINITION,
    SEND_VOICE_TOOL_DEFINITION,
    WORKSPACE_RUN_TOOL_DEFINITION,
    WORKSPACE_WRITE_TOOL_DEFINITION,
    WORKSPACE_READ_TOOL_DEFINITION,
    WORKSPACE_LIST_TOOL_DEFINITION
]

async def ask_llm(
    session_key: str,
    sender_name: str,
    user_msg: str,
    image_urls: Optional[List[str]] = None,
    recent_context: Optional[str] = None
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    自主 Agent 决策与自反思主流程。
    返回: (reply_text, generated_svg_png_b64)
    若发生不可逆异常，返回萌系友好兜底文案，绝不静默失联。
    """
    client = get_llm_client()
    history_messages = get_session_history(session_key)

    system_content = f"{PROMPT_CATGIRL_BASE}\n\n{get_utc8_wall_clock()}"
    messages_to_send = [{"role": "system", "content": system_content}]
    messages_to_send.extend(history_messages)

    current_text = f"{sender_name}: {user_msg}" if user_msg else f"{sender_name}: 发了张图"
    if recent_context:
        prompt_text = f"{recent_context}\n\n【当前消息】\n{current_text}"
    else:
        prompt_text = current_text

    # 多模态图片直接透传 (支持直接 HTTP/HTTPS URL 与 Base64 混合输入)
    valid_images = []
    if image_urls:
        target_urls = image_urls[:MAX_IMAGES_PER_TURN]
        for u in target_urls:
            clean_u = html.unescape(u).strip()
            if clean_u.startswith("http://") or clean_u.startswith("https://") or clean_u.startswith("data:image"):
                valid_images.append(clean_u)
            else:
                # 若为本地文件或特殊路径，通过 base64 转换兜底
                b64 = await fetch_image_as_base64(clean_u)
                if b64:
                    valid_images.append(b64)
        print(f"[*] 成功装载多模态视觉输入: {len(valid_images)} / {len(target_urls)} 张 (直接传图)")

    if valid_images:
        content_parts = [{"type": "text", "text": prompt_text}]
        for img_entry in valid_images:
            content_parts.append({"type": "image_url", "image_url": {"url": img_entry}})
        messages_to_send.append({"role": "user", "content": content_parts})
    else:
        messages_to_send.append({"role": "user", "content": prompt_text})

    try:
        try:
            # 第一轮决策推演
            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages_to_send,
                tools=ALL_AGENT_TOOLS,
                tool_choice="auto",
                max_tokens=700,
                temperature=0.85,
            )
        except Exception as e_first:
            err_str = str(e_first)
            # 容错：如果群聊回溯的旧图片直链过期触发 404，自动降级为纯文本重试，绝不报错中断
            if valid_images and ("404" in err_str or "Cannot fetch content" in err_str or "NotFoundError" in type(e_first).__name__):
                print(f"[-] 检测到失效历史图片直链，自动降级为纯文本重试: {e_first}")
                messages_to_send[-1] = {"role": "user", "content": prompt_text}
                valid_images = []
                response = await client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages_to_send,
                    tools=ALL_AGENT_TOOLS,
                    tool_choice="auto",
                    max_tokens=700,
                    temperature=0.85,
                )
            else:
                raise e_first
        current_msg = response.choices[0].message

        generated_svg_b64 = None
        generated_voice_b64 = None
        active_candidate_images = []
        reply = ""

        # 自主 Agent 多轮思考、工具调用与视觉重绘循环 (上限 10 轮，模型自主决定何时收敛)
        for step in range(15):
            if not current_msg.tool_calls:
                reply = (current_msg.content or "").strip()
                print(f"[*] Agent 自主决定收敛完成 (轮次 {step})，正在组织最终回复...")
                break

            print(f"[*] Agent 自主循环 (轮次 {step+1}/15): 触发 {len(current_msg.tool_calls)} 个工具调用")
            messages_to_send.append(current_msg)

            for tc in current_msg.tool_calls:
                fn_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}

                if fn_name == "tavily_search":
                    q = args.get("query", "") if isinstance(args, dict) else str(tc.function.arguments)
                    print(f"[*] 执行 Tavily 联网检索 (轮次 {step+1}): {q}")
                    search_res = await perform_tavily_search(q)
                    messages_to_send.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": search_res
                    })
                elif fn_name == "send_voice":
                    v_text = args.get("text", "")
                    v_voice = args.get("voice", "tianmei")
                    print(f"[*] 执行海螺 AI (MiniMax) 语音合成 (轮次 {step+1}): {v_text[:30]} ({v_voice})")
                    v_b64, v_err = await generate_speech(v_text, voice_name=v_voice)
                    if v_b64:
                        generated_voice_b64 = v_b64
                        messages_to_send.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"语音已生成完毕并准备作为 QQ 语音气泡发送给用户喵！"
                        })
                    else:
                        messages_to_send.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"语音合成未成功: {v_err}"
                        })
                elif fn_name == "fetch_web_page":
                    w_url = args.get("url", "")
                    print(f"[*] 执行网页深度抓取与阅读 (轮次 {step+1}): {w_url[:60]}")
                    page_content = await fetch_web_page_content(w_url)
                    messages_to_send.append({"role": "tool", "tool_call_id": tc.id, "content": page_content})
                elif fn_name == "generate_image":
                    p_prompt = args.get("prompt", "")
                    p_ref = args.get("reference_image_url")
                    print(f"[*] 执行 AI 绘画大模型 (gemini-3.1-flash-image 并发双候选) (轮次 {step+1})")
                    
                    # 1. 结构化传参或字符串回退
                    call_param = args if (isinstance(args, dict) and len(args) > 1) else (p_prompt or str(args))
                    valid_candidates, err_msg = await generate_picture_gemini(call_param, reference_image_url=p_ref)
                    
                    if valid_candidates:
                        active_candidate_images = valid_candidates
                        # 确保默认保底为合法的纯 Base64 字符串 (防止类型泄露为 list)
                        generated_svg_b64 = valid_candidates[0]
                        
                        # 2. 【工作区有机联动】：将生成的候选画作沉淀入沙箱工作区，供脚本读取或图像分析
                        try:
                            ws_dir = workspace_manager.get_workspace_path(session_key, create=True)
                            for i_cand, c_b64 in enumerate(valid_candidates, 1):
                                cand_path = os.path.join(ws_dir, f"candidate_{i_cand}.jpg")
                                import base64 as b64_mod
                                with open(cand_path, "wb") as f_cand:
                                    f_cand.write(b64_mod.b64decode(c_b64))
                            print(f"[+] 候选画作已有机归档至沙箱工作区: {ws_dir}")
                        except Exception as e_ws:
                            print(f"[-] 候选画作写入工作区异常: {e_ws}")

                        messages_to_send.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"AI 绘画已成功并发生成 {len(valid_candidates)} 张不同视角的候选图，并已归档至沙箱工作区 (candidate_1.jpg, candidate_2.jpg)！"
                        })
                        
                        # 3. 视觉回显双候选自检比选
                        reflection_parts = [
                            {
                                "type": "text",
                                "text": (
                                    f"【视觉回显自检与多候选比选把关】本次为你并发生成了 {len(valid_candidates)} 张不同视角的候选图喵！\n"
                                    "请用你的眼睛仔细审阅对比（重点检查：是否有三只手、多余手臂/手指、五官融化等肢体畸形，以及是否严格还原了名场面设定）：\n"
                                    "- 如果【候选图1】肢体解剖更正常、人物特征与情感氛围更符合剧情，在回复正文中明确标注 [SELECT_1]；\n"
                                    "- 如果【候选图2】肢体解剖更正常、人物特征与情感氛围更符合剧情，在回复正文中明确标注 [SELECT_2]；\n"
                                    "请比选出最完美的一张，并在图解赏析中客观指出亮点与小瑕疵喵。"
                                )
                            }
                        ]
                        for idx_c, c_b64 in enumerate(valid_candidates, 1):
                            reflection_parts.append({"type": "text", "text": f"--- 候选图 {idx_c} ---"})
                            reflection_parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{c_b64}"}})
                        messages_to_send.append({"role": "user", "content": reflection_parts})
                    else:
                        print(f"[-] AI 绘图未能生成: {err_msg}")
                        messages_to_send.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"AI 绘画未能生成: {err_msg}。请向用户说明情况，或者自主转用 draw_svg 绘制矢量图说明。"
                        })
                elif fn_name == "workspace_run":
                    cmd = args.get("command", "")
                    print(f"[*] 执行沙箱命令 (轮次 {step+1}): {cmd[:50]}")
                    code_ret, out_str, err_str = workspace_manager.run_command(session_key, cmd)
                    res_text = f"退出码: {code_ret}\n标准输出:\n{out_str or '(无输出)'}\n标准错误:\n{err_str or '(无错误)'}"
                    messages_to_send.append({"role": "tool", "tool_call_id": tc.id, "content": res_text})
                elif fn_name == "workspace_write":
                    fname = args.get("filename", "")
                    fcontent = args.get("content", "")
                    print(f"[*] 写入沙箱文件 (轮次 {step+1}): {fname} ({len(fcontent)} 字符)")
                    ok, msg_res = workspace_manager.write_file(session_key, fname, fcontent)
                    messages_to_send.append({"role": "tool", "tool_call_id": tc.id, "content": msg_res})
                elif fn_name == "workspace_read":
                    fname = args.get("filename", "")
                    print(f"[*] 读取沙箱文件 (轮次 {step+1}): {fname}")
                    ok, msg_res = workspace_manager.read_file(session_key, fname)
                    messages_to_send.append({"role": "tool", "tool_call_id": tc.id, "content": msg_res})
                elif fn_name == "workspace_list":
                    print(f"[*] 查看沙箱文件清单 (轮次 {step+1})")
                    items = workspace_manager.list_files(session_key)
                    res_content = json.dumps(items, ensure_ascii=False) if items else "沙箱工作区当前为空。"
                    messages_to_send.append({"role": "tool", "tool_call_id": tc.id, "content": res_content})
                elif fn_name == "draw_svg":
                    svg_title = args.get("title", "示意图")
                    svg_code = args.get("svg_code", "")
                    print(f"[*] 执行 SVG 绘图与渲染 (轮次 {step+1}): {svg_title}")
                    b64_img, err_msg = render_svg_to_png_base64(svg_code)
                    if b64_img:
                        generated_svg_b64 = b64_img
                        messages_to_send.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"SVG 已成功光栅化渲染为高清 PNG（标题: {svg_title}，大小: {len(b64_img)}字节）。"
                        })
                        # 视觉回显反馈：将渲染出的图片喂给模型，让其自检是否需要重绘优化
                        messages_to_send.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"【视觉回显自检】这是你刚才绘制的『{svg_title}』渲染出来的实际效果图喵！请审视线条、构图与细节：如果觉得还需要微调优化，可再次调用 draw_svg 重新重绘；如果觉得已经很完美，请直接进行最终的图解与总结输出。"
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{b64_img}"}
                                }
                            ]
                        })
                    else:
                        messages_to_send.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"SVG 渲染未成功: {err_msg}。请调整 SVG 代码或直接向用户说明。"
                        })

            next_resp = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages_to_send,
                tools=ALL_AGENT_TOOLS,
                tool_choice="auto",
                max_tokens=700,
                temperature=0.85,
            )
            current_msg = next_resp.choices[0].message
        else:
            reply = (current_msg.content or "").strip()

        # 若达到上限仍未产生文本，强制无工具总结
        if not reply:
            print("[*] 工具调用已达上限，正在强制进行总结回复生成...")
            final_resp = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages_to_send,
                max_tokens=700,
                temperature=0.85,
            )
            reply = (final_resp.choices[0].message.content or "").strip()

        # 审美自检验收与多候选比选 (永远不吞图，确保用户总能收到最佳画面产物)
        if "[SELECT_2]" in reply and len(active_candidate_images) >= 2:
            print("[+] 模型自检选中【候选图 2】出站！")
            generated_svg_b64 = active_candidate_images[1]
        elif "[SELECT_1]" in reply and len(active_candidate_images) >= 1:
            print("[+] 模型自检选中【候选图 1】出站！")
            generated_svg_b64 = active_candidate_images[0]
        elif active_candidate_images:
            # 即使模型觉得存在瑕疵，也始终放行两张中更优的一张出站，坚决杜绝“把图吞掉只发文字”的恶性体验！
            print("[*] 模型自检完成，放行最佳候选画面出站 (杜绝吞图)！")
            generated_svg_b64 = active_candidate_images[0]

        reply = re.sub(r"\[SELECT_[12]\]|\[REJECT_ALL\]|\[REJECT_IMAGE\]|\[ACCEPT_IMAGE\]", "", reply, flags=re.I).strip()

        # 兜底：若模型正文包含裸 SVG 代码，自动渲染为图片并剥离 XML
        if not generated_svg_b64 and ("<svg" in reply.lower() and "</svg>" in reply.lower()):
            svg_match = re.search(r"<svg[\s\S]*?</svg>", reply, flags=re.I)
            if svg_match:
                b64_img, _ = render_svg_to_png_base64(svg_match.group(0))
                if b64_img:
                    generated_svg_b64 = b64_img
                    reply = re.sub(r"```(?:xml|svg)?\s*<svg[\s\S]*?</svg>\s*```", "", reply, flags=re.I)
                    reply = re.sub(r"<svg[\s\S]*?</svg>", "", reply, flags=re.I).strip()
                    if not reply:
                        reply = "给，阿橘已经用爪子画好并渲染出来啦喵~ 🐾"

        # 存入短期长程历史 (裁剪过长文本，避免 token 爆炸)
        user_history_text = user_msg
        if len(user_history_text) > 300:
            user_history_text = user_history_text[:300] + "...[长文本已折叠]"
        if valid_images:
            user_history_text += f" [包含 {len(valid_images)} 张图片]"

        append_to_history(session_key, f"{sender_name}: {user_history_text}", reply)

        return reply, generated_svg_b64, generated_voice_b64

    except Exception as e:
        print(f"[API 异常]: {type(e).__name__}: {e}")
        # 优雅降级：向用户输出友好萌系错误提示，绝不在聊天中失联
        fallback_reply = "喵呜... 思考的时候网络小海豚打了个盹，阿橘没能连上大脑喵！请主人稍后再呼唤我试一次吧🐾"
        return fallback_reply, None, None
