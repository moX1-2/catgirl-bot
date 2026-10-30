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
        "description": "调用海螺 AI (MiniMax T2A v2 旗舰级拟真语音) 用阿橘的原声向用户发语音条。剧本写法秘诀：多用波浪线'~'拉长甜美元音，省略号'……'产生自然呼吸停顿，短句搭配逗号，建议 5~35 字以内，杜绝拗口长句！",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "要朗诵的语音台词剧本。善用拟声词（如'喵呜~'、'嘻嘻'）、波浪号'~'与省略号'……'，情感鲜活生动！"
                },
                "voice": {
                    "type": "string",
                    "enum": ["tianmei", "shaonv", "yujie", "boy"],
                    "description": "音色选择。tianmei: 甜美少女/猫娘音(默认最推荐); shaonv: 元气活泼少女; yujie: 温柔御姐; boy: 活力少年。"
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
        "description": "【方案B：AI 绘画大模型 (gemini-3.1-flash-image 结构化生图引擎)】并发生成 2 张候选图供视觉自检比选 (Best-of-N)。采用结构化字段由你直接指定画面类别、主体、动作与场景，系统将自动确定性加载对应领域的物理与解剖守卫！",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "sports_athletics",
                        "multi_character_intimate",
                        "single_character_portrait",
                        "general_anime_art"
                    ],
                    "description": "画面语义分类 (至关重要！): sports_athletics(球类/运动竞技，将自动激活严格单球物理守卫); multi_character_intimate(双人/多人亲密互动，如接吻/拥抱，自动激活侧颜防融化与肢体防粘连守卫); single_character_portrait(单人立绘，激活动态姿态与电影构图); general_anime_art(通用插画/风景)"
                },
                "subject": {
                    "type": "string",
                    "description": "画面核心主体（如：昔涟与爱莉希雅、流萤、琪亚娜与芽衣）"
                },
                "action_and_pose": {
                    "type": "string",
                    "description": "角色的生动具体动作与姿态（如：昔涟飞身扑救、爱莉希雅起跳扣杀；双人亲吻必须采用侧颜视角 profile view 避免五官融化）"
                },
                "setting_and_scene": {
                    "type": "string",
                    "description": "用户指定的具体背景与环境（如：夏日阳光沙滩排球场、微风草地、夕阳天台），背景会被严格锁定，防止被参考图污染！"
                },
                "reference_image_url": {
                    "type": "string",
                    "description": "官方参考图 HTTP/HTTPS 直链（用于角色发型/配色对齐，背景会被自动隔离）"
                },
                "prompt": {
                    "type": "string",
                    "description": "补充的画面氛围、光影与英文细节提示词（可选）"
                }
            },
            "required": ["category", "subject", "action_and_pose"]
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

FETCH_WEB_PAGE_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "fetch_web_page",
        "description": "访问并深度抓取指定网页的完整正文内容。当 tavily_search 检索到的摘要不够详尽，或者需要深入阅读某个搜索结果链接的具体技术细节、博客文章、完整设定、GitHub文档或长文报道时调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取阅读的目标网页完整 HTTP/HTTPS 链接"
                }
            },
            "required": ["url"]
        }
    }
}

PLAY_MUSIC_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "play_music",
        "description": "【方案1：纯原生语音点歌】在酷我/网易云等全网曲库中搜索音乐并以 QQ 原生语音气泡直接向聊天中播发歌曲。当用户想要听歌、点歌、放背景音乐、或表达特定旋律时调用此工具。零卡片拦截风险，点击直接畅听整首！",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "歌曲名称或'歌名 歌手'，例如 '晴天'、'起风了 买辣椒也用券'、'告白气球 周杰伦'"
                }
            },
            "required": ["keyword"]
        }
    }
}
