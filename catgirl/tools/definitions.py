# -*- coding: utf-8 -*-
"""
Agent Function Calling 工具定义
"""

DRAW_SVG_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "draw_svg",
        "description": "【方案A：SVG 矢量制图 (无频率限制/速度秒级)】绘制结构清晰的矢量图并自动光栅化为高清图片。最适用于：系统架构图、流程逻辑图、技术对比卡片、数据示意图、UI排版框架或简笔线条猫猫涂鸦。优势：秒级生成、中文字体排版精准、无生成频率限制。当内容偏向逻辑、排版、图表、卡片时优先选择此工具。",
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

SEND_VOICE_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "send_voice",
        "description": "用小橘萌萌的原声语音说话并发送语音条给用户。适用于：用户要求语音、发语音、听你说、撒娇、唱歌、念台词，或者你想用真实声音软萌互动的情境。",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "要用语音说出的文本内容，建议 5~40 字以内，自然口语化，适合猫娘声线表达。"
                },
                "voice": {
                    "type": "string",
                    "enum": ["Aoede", "Kore", "Puck"],
                    "description": "音色选择。Aoede: 活泼元气猫娘少女音(推荐默认); Kore: 温柔安静学姐音; Puck: 少年音。"
                }
            },
            "required": ["text"]
        }
    }
}

GENERATE_IMAGE_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": "【方案B：AI 绘画大模型 (gemini-3.1-flash-image)】调用专业绘图大模型绘制精美复杂图像。最适用于：二次元插画、写实场景、艺术画作、精美壁纸、逼真萌宠或复杂人物角色绘制。注意：该工具受到严格的 1 分钟 1 张频率保护，耗时约 30~50 秒。当用户需要精美插画、绘画或写实艺术作品时选用此工具。你可以自主在 draw_svg (排版/图表/架构/简笔) 与 generate_image (精美插画/写实艺术) 之间权衡决策！",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "详细生动的英文或中文画面描述提示词（建议包含画面主体、艺术风格、光影色彩、构图细节）"
                }
            },
            "required": ["prompt"]
        }
    }
}

WORKSPACE_RUN_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "workspace_run",
        "description": "在会话专属的安全沙箱工作区中执行命令或运行脚本 (如运行 Python 数据计算、处理文本、批量清洗等)。禁止逃逸或破坏操作，自带超时强杀释放保护。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要在沙箱工作区中执行的终端或解释器命令，例如 'python3 script.py' 或 'ls -la'"
                }
            },
            "required": ["command"]
        }
    }
}

WORKSPACE_WRITE_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "workspace_write",
        "description": "在沙箱工作区中创建或覆盖写入文件。受严格单文件大小与沙箱路径防逃逸保护。",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "相对路径文件名，例如 'calc.py' 或 'data/test.json'"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文件完整文本内容"
                }
            },
            "required": ["filename", "content"]
        }
    }
}

WORKSPACE_READ_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "workspace_read",
        "description": "从沙箱工作区中读取文件文本内容。受防逃逸检查限制。",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "要读取的文件相对路径名"
                }
            },
            "required": ["filename"]
        }
    }
}

WORKSPACE_LIST_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "workspace_list",
        "description": "列出当前沙箱工作区中的所有文件与目录清单及体积状态。",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}
