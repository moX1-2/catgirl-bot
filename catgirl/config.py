# -*- coding: utf-8 -*-
"""
小橘 Agent 基础配置与运行常量
支持从系统环境变量或 .env 文件加载，所有敏感信息均已解耦
"""

import os

# 自动寻找并加载 .env 配置文件 (兼容本地开发与生产部署)
_possible_env_paths = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    os.path.join(os.getcwd(), ".env")
]

for _env_path in _possible_env_paths:
    if os.path.isfile(_env_path):
        try:
            with open(_env_path, "r", encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith("#") and "=" in _line:
                        _k, _v = _line.split("=", 1)
                        os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))
        except Exception:
            pass
        break

# 大模型 API 配置 (OpenAI 协议兼容，如 Gemini、DeepSeek、GPT 等)
API_KEY = os.getenv("LLM_API_KEY", "")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gemini-3.8-flash-medium")
IMAGE_GEN_MODEL = os.getenv("IMAGE_GEN_MODEL", "gemini-3.1-flash-image")  # AI 绘图生图大模型
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60.0"))  # 异步请求超时时间 (秒)
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))

# QQ 与 OneBot 11 协议配置
BOT_QQ = os.getenv("BOT_QQ", "")
ADMIN_QQ = os.getenv("ADMIN_QQ", "")
ONEBOT_WS_URI = os.getenv("ONEBOT_WS_URI", "ws://127.0.0.1:3001")

# 多模态会话配置
MAX_IMAGES_PER_TURN = int(os.getenv("MAX_IMAGES_PER_TURN", "16"))
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "7"))
SESSION_EXPIRE_SECONDS = int(os.getenv("SESSION_EXPIRE_SECONDS", "600"))
GROUP_SESSION_MODE = os.getenv("GROUP_SESSION_MODE", "user")  # "user" 为单人隔离模式, "group" 为全群共享
GROUP_CONTEXT_LIMIT = int(os.getenv("GROUP_CONTEXT_LIMIT", "20"))

# 心跳保活
ENABLE_HEARTBEAT = os.getenv("ENABLE_HEARTBEAT", "true").lower() in ("true", "1", "yes")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "300"))

# 长回复折叠配置 (文本过长时自动打包为一条合并转发聊天记录，保持群聊整洁)
FORWARD_FOLD_ENABLED = os.getenv("FORWARD_FOLD_ENABLED", "true").lower() in ("true", "1", "yes")
FORWARD_FOLD_THRESHOLD = int(os.getenv("FORWARD_FOLD_THRESHOLD", "260"))  # 超过260字自动收起
FORWARD_FOLD_LINES = int(os.getenv("FORWARD_FOLD_LINES", "6"))           # 超过6行自动收起

# Gemini 3.8 Flash TTS 语音合成密钥与音调系数
GEMINI_TTS_KEY = os.getenv("GEMINI_TTS_KEY", "")
TTS_PITCH_FACTOR = float(os.getenv("TTS_PITCH_FACTOR", "1.15"))  # 默认 1.15x 升调，达到最佳自然猫娘萌化效果

# Tavily 搜索密钥池 (支持逗号分隔多个 Key 自动故障转移)
_tavily_raw = os.getenv("TAVILY_KEYS", "")
if _tavily_raw:
    TAVILY_KEYS = [k.strip() for k in _tavily_raw.split(",") if k.strip()]
else:
    TAVILY_KEYS = []

# 临时工作区与隔离沙箱配置 (安全路径防逃逸、配额防打爆、超时强杀、生命周期全自动释放)
WORKSPACE_BASE_DIR = os.getenv("WORKSPACE_BASE_DIR", "/tmp/catgirl_workspaces")
WORKSPACE_MAX_FILE_SIZE_MB = int(os.getenv("WORKSPACE_MAX_FILE_SIZE_MB", "5"))   # 单文件最大 5MB
WORKSPACE_MAX_TOTAL_MB = int(os.getenv("WORKSPACE_MAX_TOTAL_MB", "30"))          # 单工作区总额 30MB
WORKSPACE_CMD_TIMEOUT_SEC = float(os.getenv("WORKSPACE_CMD_TIMEOUT_SEC", "15.0")) # 命令执行超时 15秒
WORKSPACE_TTL_SECONDS = int(os.getenv("WORKSPACE_TTL_SECONDS", "1800"))           # 闲置半小时自动彻底清理释放

# 速率限制配置
TAVILY_MAX_PER_MINUTE = int(os.getenv("TAVILY_MAX_PER_MINUTE", "10"))
TAVILY_MIN_INTERVAL = float(os.getenv("TAVILY_MIN_INTERVAL", "1.0"))
DM_LIMIT_PER_MINUTE = int(os.getenv("DM_LIMIT_PER_MINUTE", "5"))

# 关键词唤醒概率
FISH_TRIGGER_PROBABILITY = float(os.getenv("FISH_TRIGGER_PROBABILITY", "0.3"))  # 「鱼」关键词 30% 概率触发
