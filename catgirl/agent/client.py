# -*- coding: utf-8 -*-
"""
大模型客户端单例与双协议驱动引擎
支持 Google Generative Language REST 原生协议 与 OpenAI 兼容协议 无缝平滑切换。
可通过环境变量 LLM_PROTOCOL="google" (推荐: 支持原生视频/原生音频/思维链) 或 "openai" (通用兼容) 控制。
"""

import os
import json
import base64
import html
import asyncio
from typing import List, Dict, Any, Optional, Tuple

import httpx
from openai import AsyncOpenAI
from ..config import (
    API_KEY,
    BASE_URL,
    MODEL_NAME,
    LLM_TIMEOUT,
    LLM_MAX_RETRIES,
    LLM_PROTOCOL
)


class UnifiedFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class UnifiedToolCall:
    def __init__(self, call_id: str, name: str, arguments: str):
        self.id = call_id
        self.function = UnifiedFunction(name, arguments)
        self.type = "function"


class UnifiedMessage:
    def __init__(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[UnifiedToolCall]] = None,
        thought: Optional[str] = None
    ):
        self.content = content or ""
        self.tool_calls = tool_calls
        self.thought = thought
        self.role = "assistant"


class UnifiedChoice:
    def __init__(self, message: UnifiedMessage):
        self.message = message


class UnifiedResponse:
    def __init__(self, message: UnifiedMessage):
        self.choices = [UnifiedChoice(message)]


def _convert_schema_to_google(schema: Any) -> Any:
    """递归将 JSON Schema 类型转为 Google 原生的大写枚举"""
    if not isinstance(schema, dict):
        return schema
    res = dict(schema)
    if "type" in res and isinstance(res["type"], str):
        res["type"] = res["type"].upper()
    if "properties" in res and isinstance(res["properties"], dict):
        res["properties"] = {k: _convert_schema_to_google(v) for k, v in res["properties"].items()}
    if "items" in res and isinstance(res["items"], dict):
        res["items"] = _convert_schema_to_google(res["items"])
    return res


def _convert_tools_to_google(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """将 OpenAI 格式的 tools 转换为 Google functionDeclarations"""
    if not tools:
        return None
    declarations = []
    for t in tools:
        fn = t.get("function", {})
        if not fn:
            continue
        declarations.append({
            "name": fn.get("name"),
            "description": fn.get("description", ""),
            "parameters": _convert_schema_to_google(fn.get("parameters", {"type": "object", "properties": {}}))
        })
    return [{"functionDeclarations": declarations}] if declarations else None


async def _convert_messages_to_google(messages: List[Any]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    将 OpenAI 格式的消息列表转换为 Google Generative Language 原生结构:
    支持自动下载与转换 HTTP/HTTPS 图片为 inline_data (解决'图片直链肉眼看不了'Bug)
    返回 (system_instruction, contents)
    """
    system_parts = []
    contents = []

    for msg in messages:
        # 兼容字典对象与 UnifiedMessage 对象
        if hasattr(msg, "role"):
            role = msg.role
            content = msg.content
            tool_calls = getattr(msg, "tool_calls", None)
            tool_call_id = None
        else:
            role = msg.get("role")
            content = msg.get("content")
            tool_calls = msg.get("tool_calls")
            tool_call_id = msg.get("tool_call_id")

        if role == "system":
            if isinstance(content, str) and content.strip():
                system_parts.append({"text": content.strip()})
            elif isinstance(content, list):
                for p in content:
                    if isinstance(p, dict) and p.get("text"):
                        system_parts.append({"text": p["text"]})

        elif role == "user":
            user_parts = []
            if isinstance(content, str):
                if content:
                    user_parts.append({"text": content})
            elif isinstance(content, list):
                for p in content:
                    if not isinstance(p, dict):
                        continue
                    p_type = p.get("type")
                    if p_type == "text":
                        t_val = p.get("text", "")
                        if t_val:
                            user_parts.append({"text": t_val})
                    elif p_type == "image_url":
                        url_val = p.get("image_url", {}).get("url", "")
                        if url_val.startswith("data:"):
                            try:
                                header, b64_data = url_val.split(",", 1)
                                mime = header.split(";")[0].replace("data:", "").strip()
                                user_parts.append({
                                    "inline_data": {
                                        "mime_type": mime,
                                        "data": b64_data
                                    }
                                })
                            except Exception:
                                pass
                        elif url_val.startswith("base64://"):
                            user_parts.append({
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": url_val.replace("base64://", "")
                                }
                            })
                        elif url_val.startswith("http"):
                            # 核心修复：纯 HTTP 图片自动经由 fetch_image_as_base64 异步下载并转为 inline_data!
                            try:
                                from ..tools.image import fetch_image_as_base64
                                b64 = await fetch_image_as_base64(url_val)
                                if b64 and b64.startswith("data:"):
                                    header, b64_data = b64.split(",", 1)
                                    mime = header.split(";")[0].replace("data:", "").strip()
                                    user_parts.append({
                                        "inline_data": {
                                            "mime_type": mime,
                                            "data": b64_data
                                        }
                                    })
                                else:
                                    user_parts.append({"text": f"[图片直链]: {url_val}"})
                            except Exception as e_dl:
                                print(f"[-] 转换 HTTP 图片为 inline_data 失败: {e_dl}")
                                user_parts.append({"text": f"[图片直链]: {url_val}"})
                    elif p_type == "video_data":
                        # 原生视频直传
                        user_parts.append({
                            "inline_data": {
                                "mime_type": p.get("mime_type", "video/mp4"),
                                "data": p.get("data", "")
                            }
                        })
            if user_parts:
                contents.append({"role": "user", "parts": user_parts})

        elif role in ("assistant", "model"):
            model_parts = []
            if content and isinstance(content, str) and content.strip():
                model_parts.append({"text": content.strip()})
            if tool_calls:
                for tc in tool_calls:
                    fn_name = tc.function.name if hasattr(tc, "function") else tc.get("function", {}).get("name")
                    fn_args_raw = tc.function.arguments if hasattr(tc, "function") else tc.get("function", {}).get("arguments", "{}")
                    try:
                        parsed_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                    except Exception:
                        parsed_args = {}
                    model_parts.append({
                        "functionCall": {
                            "name": fn_name,
                            "args": parsed_args
                        }
                    })
            if model_parts:
                contents.append({"role": "model", "parts": model_parts})

        elif role == "tool":
            # 工具执行结果回显
            t_content = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            tool_name = "tool_response"
            # 尝试回溯上一次调用的函数名
            if contents and contents[-1].get("role") == "model":
                for part in contents[-1].get("parts", []):
                    if "functionCall" in part:
                        tool_name = part["functionCall"].get("name", tool_name)
            contents.append({
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": tool_name,
                            "response": {"content": t_content}
                        }
                    }
                ]
            })

    sys_instruction = {"parts": system_parts} if system_parts else None
    return sys_instruction, contents


class GoogleCompletionsAdapter:
    """基于 Google Generative Language REST 协议的异步适配器"""

    def __init__(self, api_key: str, base_url: str, timeout: float):
        self.api_key = api_key
        # 清洗 base_url，截取基础域名 (去除 /v1 等 OpenAI 后缀)
        clean_base = base_url.rstrip("/")
        if clean_base.endswith("/v1"):
            clean_base = clean_base[:-3]
        self.base_url = clean_base
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15.0, read=timeout, write=30.0, pool=40.0)
        )

    async def create(
        self,
        model: str,
        messages: List[Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        max_tokens: int = 700,
        temperature: float = 0.85,
        **kwargs
    ) -> UnifiedResponse:
        system_instruction, contents = await _convert_messages_to_google(messages)
        google_tools = _convert_tools_to_google(tools)

        payload: Dict[str, Any] = {"contents": contents}
        if system_instruction:
            payload["system_instruction"] = system_instruction
        if google_tools:
            payload["tools"] = google_tools

        payload["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }

        endpoint_url = f"{self.base_url}/v1beta/models/{model}:generateContent?key={self.api_key}"

        response = await self.client.post(
            endpoint_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return UnifiedResponse(UnifiedMessage(content=""))

        cand = candidates[0]
        parts = cand.get("content", {}).get("parts", [])

        content_text = ""
        thought_text = ""
        tool_calls = []

        for p in parts:
            if p.get("thought"):
                thought_text += p.get("text", "")
            elif p.get("text"):
                content_text += p.get("text", "")
            elif p.get("functionCall"):
                fc = p["functionCall"]
                fn_name = fc.get("name", "")
                fn_args = json.dumps(fc.get("args", {}), ensure_ascii=False)
                call_id = fc.get("id") or f"call_{len(tool_calls)+1}"
                tool_calls.append(UnifiedToolCall(call_id, fn_name, fn_args))

        msg = UnifiedMessage(
            content=content_text,
            tool_calls=tool_calls if tool_calls else None,
            thought=thought_text if thought_text else None
        )
        return UnifiedResponse(msg)


class DualProtocolChat:
    def __init__(self, completions_impl):
        self.completions = completions_impl


class DualProtocolClient:
    """双协议客户端代理：透明支持 client.chat.completions.create(...) 调用"""
    def __init__(self, completions_impl):
        self.chat = DualProtocolChat(completions_impl)


_dual_client: Optional[DualProtocolClient] = None


def get_llm_client() -> Any:
    """获取大模型驱动客户端 (根据 LLM_PROTOCOL 自动选择 Google 或 OpenAI 协议)"""
    global _dual_client
    if _dual_client is None:
        if LLM_PROTOCOL == "google":
            print(f"[+] 正在初始化 Google Generative Language 原生协议驱动 (端点: {BASE_URL}, 模型: {MODEL_NAME})")
            adapter = GoogleCompletionsAdapter(
                api_key=API_KEY,
                base_url=BASE_URL,
                timeout=LLM_TIMEOUT
            )
            _dual_client = DualProtocolClient(adapter)
        else:
            print(f"[+] 正在初始化 OpenAI 兼容协议客户端 (端点: {BASE_URL}, 模型: {MODEL_NAME})")
            openai_native = AsyncOpenAI(
                api_key=API_KEY,
                base_url=BASE_URL,
                timeout=httpx.Timeout(connect=15.0, read=LLM_TIMEOUT, write=20.0, pool=30.0),
                max_retries=LLM_MAX_RETRIES
            )
            _dual_client = openai_native

    return _dual_client
