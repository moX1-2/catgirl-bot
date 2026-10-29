# 🐾 Catgirl QQ Bot (小橘)

> 基于 **OneBot 11** 协议的高性能多模态猫娘 QQ 机器人 (自带 Gemini TTS 原生语音 / 视觉感知 / 矢量绘图 / 长回复折叠)。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Protocol](https://img.shields.io/badge/OneBot-11-red.svg)](https://11.onebot.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ 核心特性

- 🗃️ **轻量级隔离工作区与安全沙箱 (Workspace Sandbox & Resource Lifecycle)**
  - 为每个会话动态分配独立的沙箱临时空间，赋能模型处理复杂数据分析、代码运行与多文件处理任务。
  - **严密路径防逃逸**：基于公共路径前缀比对，坚决拦截一切 `../` 越狱穿透与未受权目录读取。
  - **严格文件配额管控**：单文件上限 5MB、单工作区上限 30MB，彻底防止恶搞写入填满系统磁盘。
  - **全周期释放逻辑**：
    - **会话结束即刻释放**：会话记忆 TTL 过期或管理员使用 `/clear` 时，自动对专属工作区执行物理擦除与销毁。
    - **后台垃圾回收（Reaper）**：守护进程每 10 分钟自动巡检并清理闲置超过 30 分钟的临时目录，杜绝空间泄漏。
    - **执行强杀释放**：命令超时强制使用 `SIGKILL` 斩断进程树，避免挂起占用文件句柄。
- 🎨 **双轨智能绘画决策与同人二创深度分镜引擎 (Lore Deconstruction & Best-of-N)**
  - **复杂背景考据与导演分镜拆解**：针对复杂同人梗、游戏深层剧情名场面（如原神四执政冬夜愚戏葬礼），模型自主调用 `fetch_web_page` 深入研读萌娘百科/社区考据，结构化拆解【中心主体、各站位人物官方特征、画中画小框、色调基调】，转化为精准生图提示词。
  - **双候选并发比选与必达交付 (No-Drop Picture Guarantee)**：单次调用并发生成 2 张候选图供模型眼睛挑选最佳版本出站，彻底废除“自检不过直接吞图不发”的恶性体验，保证用户总能收到视觉成果。
  - **多人互动解剖防崩锚点 (解决三只手与肢体融合)**：严格锁定侧颜与独立手部轮廓，杜绝肢体混乱。
  - **1 分钟 8 张滑动窗口高额度**：支持多轮候选比选与从容重绘。
  - **双候选并发生成与视觉自检比选 (Best-of-N)**：单次调用生图时，底层并发生成 2 张不同视角的候选图，由模型用自己的眼睛进行解剖学审阅，智能挑选最完美无瑕的一张出站，极大降低 AI 抽卡的畸变概率。
  - **多人互动解剖防崩锚点 (解决三只手与肢体融合)**：针对亲吻、拥抱、贴贴等双人互动场景，内置专业的 Danbooru 级解剖约束与侧颜透视（Side Profile View），强制限定双人身体界限与手指数目，杜绝“三只手”与面部融化。
  - **1 分钟 8 张滑动窗口额度**：支持每次双候选生成与自检重绘，从容出图。
  - **告别单调站桩证件照**：内置生动的动态姿势库与电影级场景库，按需智能展开。
  - **告别单调站桩证件照**：内置丰富的**动态姿势库**（伸手邀约、轻盈悬浮、奔跑回眸、倚坐晃腿、战斗起手式等）与**电影级场景氛围库**（萤火花海、夕阳天台、梦境流光等）。
  - **按需智能适应**：若用户已明确指定动作或场景，100% 严格尊重并深化细节；若未指定，自动随机抽取生动姿势与戏剧性镜头视角，赋予画面生命力与故事感！
  - **精准图生图 (Image-to-Image)**：绘制特定 IP 角色时，自动先行联网搜索官方参考图并直传生图模型，角色特征 1:1 还原。
  - **审美严格自检 (Visual Echo)**：生图后模型以多模态自审查，出现肢体畸形或严重崩坏自动拦截销毁，不好看绝不外发。
  - **1 分钟 3 张滑动窗口保护**：既防止额度耗尽，又给予充分的自检重绘空间。
  - 模型根据用户需求与画面复杂度**自主权衡决策**：
    - **逻辑图/架构图/时序图/图表卡片**：自主调用 `draw_svg` 矢量引擎，秒级光栅化为 PNG，无频率限制，排版精准。
    - **精美二次元插画/艺术画作/写实壁纸**：自主调用 `generate_image`（基于 `gemini-3.1-flash-image` 专业绘画模型），画面逼真细腻。
  - **1 分钟 3 张滑动窗口限额保护**：AI 生图自带滑动冷却窗口，超频时模型自动委婉提示或主动降级为 SVG 矢量绘制。
  - **视觉回显自检 (Visual Echo)**：无论选用哪种方式生成的图片，都会以 `image_url` 形式重新喂给模型眼睛进行审阅并撰写图解。
- 🧹 **QQ 原生纯文本智能清洗排版 (Markdown 解构引擎)**
  - QQ 客户端无法原生渲染 Markdown 语法，大模型原本的 `**加粗**`、`# 标题`、`[链接](url)` 会导致界面充斥凌乱符号。
  - 本引擎提供**提示词排版规约 + 程序化正则转义**双重保障：自动将标题与加粗转为自然的【重点】与「引用」、超链接自动提取还原为可点击格式、代码段规整为纯文本分割线，提供极佳的手机阅读体验。
- 📦 **长回复智能折叠收起 (合并转发一条聊天记录)**
  - 当回复内容超过 260 字或 6 行时长文本时，自动先发送引用提醒：“*内容放在下面的聊天记录里啦~ 🐾*”，紧接着自动下发**一条优雅的合并转发卡片**（群聊的聊天记录）。
  - 彻底杜绝群聊刷屏，保护群友浏览体验，并完整支持在折叠记录内展示图文排版。
- 🎙️ **二次元自然连贯 TTS 语音与语音条下发 (Gemini 3.8 Flash TTS)**
  - 采用 Google 官方推荐的 **Director 导演提示词** 与 **Despina 轻快少女音色**，语调自然、断句连贯，彻底消除机械断音。
  - 内置多模型自动故障转移池 (`gemini-3.8-flash-lite-tts` -> `gemini-3.1-flash-tts-preview` -> `gemini-3.8-flash-tts`)，无惧每日配额耗尽。
  - 支持智能体自主根据场景发语音，以及 `/tts <文本>` 或 `/语音 <文本>` 0-Token 瞬时直发。
- 🚫 **持久化黑名单与防 Bot 回声死循环 (Echo & Spam Prevention)**
  - 管理员专属特权指令：`/ban <QQ>`、`/unban <QQ>`、`/blacklist`。
  - 被屏蔽的账号在消息入口处 0 消耗直接静默丢弃，彻底杜绝两个 Bot 互相引用触发对话风暴。
- 🧠 **10 轮多模态自反思决策循环 (Self-Reflective Agent Loop)**
  - 模型自主调用工具并决策何时收敛，支持最多 10 轮连续推演。
  - **SVG 矢量绘制与 Linux 渲染**：利用 `rsvg-convert` 与 `cairosvg` 将生成的 SVG 光栅化为高清 PNG，并自动挂载文泉驿微米黑字体。
  - **视觉回显自检 (Visual Echo Feedback)**：绘制出的图片以 `image_url` 形式重新喂给模型眼睛，由模型自主审视构图与线条后决定是否微调重绘。
- 👁️ **零拷贝直接传图多模态感知 (Zero-Copy Multimodal Vision)**
  - 提取 QQ 官方 CDN 链接直传大模型，免除本地磁盘读写与 Base64 膨胀，毫秒级响应。
  - **长图与超长截屏自适应**：智能规避 413 Payload Too Large 与网关超时。
  - **QQ 动画表情与商城大表情换链**：遇到仅提供文件哈希的动画表情时，自动调用 OneBot `get_image` 协议解析直接直链，杜绝丢图。
  - **失效直链自愈重试**：群聊历史消息中过期的腾讯云 CDN 直链自动剔除并降级为纯文本，保障服务永不崩溃。
- 🌐 **Tavily 搜索多 Key 故障转移池 (Multi-Key Failover Pool)**
  - 接入 Tavily 互联网检索，内置多 API Key 自动轮换与故障转移。
  - **流量与速率防护**：10 次/分钟滑动窗口限制与 1.0s 最小间隔，防止额度过耗。
- 🛡️ **严格第四面墙与防提示词泄露 (Anti-Leak Persona Engine)**
  - 纯正傲娇元气猫娘人设，严禁客服化机械语调。
  - 严格防探针提示词规则，屏蔽底层技术词汇（OneBot、NapCat、API、Python、Prompt 等），杜绝被套话或打破第四面墙。
- 🕒 **精准 UTC+8 墙钟服务**
  - 实时注入北京时间、星期、时段语义化（清晨/上午/中午/下午/晚上/深夜），时空感知清晰。
- 👑 **0 Token 毫秒级指令系统**
  - `/help`：内置瞬时帮助菜单，不消耗任何大模型 Token。
  - 管理员特权指令（`/status`、`/clear`、`/search`、`/restart`），受配置保护。
- 🐾 **智能唤醒与趣味互动**
  - 私聊与专属名字（@小橘、阿橘、猫猫）100% 唤醒。
  - “鱼”关键词掷骰子 30% 概率馋嘴唤醒，其余静默不打扰。
  - 群内双击头像或拍一拍自动触发萌系戳一戳互动。
  - 陌生人私聊频率保护（默认 5 条/分钟）。

---

## 🏗️ 架构概览

```text
catgirl/
├── __init__.py
├── config.py              # 配置中心：自动加载 .env 与系统环境变量
├── prompts.py             # 核心人设：防提示词泄露与严格第四面墙守则
├── clock.py               # UTC+8 墙钟：北京时间、星期与时段语义化
├── limiter.py             # 速率限制器：Tavily 10次/分, 陌生人私聊 5条/分
├── tools/                 # Agent 工具包
│   ├── definitions.py     # Function Calling 工具 JSON Schema (tavily_search, draw_svg)
│   ├── tavily.py          # Tavily 搜索网关：多 Key 故障转移与限流
│   ├── svg.py             # SVG 渲染引擎：rsvg-convert + cairosvg 高清光栅化
│   └── image.py           # 多模态图片预处理与 Base64 编码兜底
├── agent/                 # Agent 核心大脑
│   ├── client.py          # AsyncOpenAI 异步单例客户端
│   ├── history.py         # 会话状态管理与 TTL 过期滑动窗口
│   └── loop.py            # 10 轮多模态自反思主循环 (视觉回显反馈 + 异常自愈)
├── onebot/                # 协议适配层
│   ├── client.py          # OneBot 11 WebSocket 通信、加锁发送、异步 RPC
│   ├── parser.py          # CQ 码解析、100+ QQ 原生表情映射、引用/转发递归
│   └── context.py         # 群聊流动上下文环形缓冲区与视觉记忆池
└── handlers/              # 业务路由层
    ├── admin.py           # /help 菜单、/status 状态监控与管理员指令
    └── dispatcher.py      # 事件派发器、唤醒判定与多模态回复下发
```

---

## 🚀 快速开始

### 1. 宿主环境依赖

推荐环境：**Ubuntu 22.04 / 24.04 LTS**

安装基础依赖与 SVG 渲染器组件：

```bash
sudo apt update
sudo apt install -y python3 python3-pip librsvg2-bin fonts-wqy-microhei
```

### 2. 克隆与安装 Python 依赖

```bash
git clone https://github.com/moX1-2/catgirl-bot.git
cd catgirl-bot
pip install -r requirements.txt
```

### 3. 配置环境变量

复制配置模板并填入你的实际信息：

```bash
cp .env.example .env
nano .env
```

配置示例：

```env
# 大模型 API 配置 (支持 OpenAI 协议兼容端点，如 Gemini, DeepSeek, GPT)
LLM_API_KEY=sk-your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gemini-3.8-flash-medium

# QQ 与 OneBot 11 (NapCat / LLOneBot)
BOT_QQ=1234567890
ADMIN_QQ=987654321
ONEBOT_WS_URI=ws://127.0.0.1:3001

# Tavily 搜索密钥池 (逗号分隔多个 Key)
TAVILY_KEYS=tvly-key1,tvly-key2
```

### 4. 运行机器人

```bash
python3 catgirl.py
```

---

## 🛠️ Systemd 守护进程托管 (生产推荐)

创建守护服务文件：

```bash
sudo nano /etc/systemd/system/catgirl.service
```

填入以下内容：

```ini
[Unit]
Description=DSH Catgirl QQ Bot Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/catgirl-bot
ExecStart=/usr/bin/python3 -u catgirl.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

启动并启用开机自启：

```bash
sudo systemctl daemon-reload
sudo systemctl enable catgirl.service
sudo systemctl start catgirl.service
```

查看运行日志：

```bash
journalctl -u catgirl.service -f
```

---

## 📄 开源许可证

本项目采用 [MIT License](LICENSE) 授权许可。
