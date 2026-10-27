# -*- coding: utf-8 -*-
"""
Agent Function Calling 工具定义
"""

DRAW_SVG_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "draw_svg",
        "description": "绘制清晰简洁的 SVG 矢量图并自动渲染为高清 PNG 图片发到聊天中。适用于绘制：系统架构图、流程逻辑图、技术对比卡片、数据示意图或猫猫插图。当用户要求画图、示意图、流程图或绘制图解时调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "图形的主题或简要描述，如 '系统架构流程图'"
                },
                "svg_code": {
                    "type": "string",
                    "description": "标准的 SVG XML 完整代码。必须包含 xmlns='http://www.w3.org/2000/svg'、width、height 与 viewBox，中文字体推荐使用 font-family='WenQuanYi Micro Hei, sans-serif'，建议使用优雅圆角底色 rect。"
                }
            },
            "required": ["title", "svg_code"]
        }
    }
}

TAVILY_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "tavily_search",
        "description": "实时在互联网检索最新信息、即时新闻、时事进展、技术资讯、天气预报或专业事实数据。当用户询问最新时事、天气、日期事实或特定前沿内容时调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或短语"
                }
            },
            "required": ["query"]
        }
    }
}
