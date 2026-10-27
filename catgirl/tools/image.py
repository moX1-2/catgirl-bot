# -*- coding: utf-8 -*-
"""
多模态图片下载与 Base64 转换服务
支持本地文件、HTTP/HTTPS、QQ 空间/CDN 防盗链与重定向
内置 Pillow 智能缩放压缩，彻底解决长图、大图、表情包爆内存与超限问题
"""

import os
import io
import ssl
import html
import base64
import asyncio
import urllib.request
import httpx
from PIL import Image

def _download_urllib(url: str, timeout: float = 15.0):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://qzone.qq.com/",
        }
    )
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return resp.read(), resp.headers.get_content_type()

def optimize_image_for_llm(raw_bytes: bytes) -> tuple[bytes, str]:
    """
    智能优化图片尺寸与体积，专门解决大图、长截图与表情包导致的传输和识别问题：
    1. 动图/GIF/WebP 多帧：提取首帧并转为高质量 RGB
    2. 透明通道 (RGBA/P)：叠加白色底色转 RGB，避免透明区域变纯黑
    3. 长图自适应 (纵横比 > 1.8)：
       - 限制宽度在 1080px 内，按比例缩放高度
       - 最大高度限制在 3840px 内（兼顾超长截图的清晰度与大模型识别率）
    4. 宽图/全景自适应 (横纵比 > 1.8)：
       - 限制高度在 1080px 内，按比例缩放宽度
       - 最大宽度限制在 3840px 内
    5. 常规大图：
       - 最大单边限制在 2048px 内
    6. 压缩为 JPEG quality=85，大幅减少 Base64 体积 (10MB -> 300KB)，避免 payload 溢出与超时
    """
    try:
        with Image.open(io.BytesIO(raw_bytes)) as im:
            # 处理动图帧
            if getattr(im, "is_animated", False):
                im.seek(0)

            # 转换为 RGB (透明底补白)
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                bg = Image.new("RGB", im.size, (255, 255, 255))
                alpha = im.convert("RGBA").split()[-1]
                bg.paste(im.convert("RGBA"), mask=alpha)
                im = bg
            elif im.mode != "RGB":
                im = im.convert("RGB")

            w, h = im.size
            if w <= 0 or h <= 0:
                return raw_bytes, "image/jpeg"

            ratio_h_w = h / w
            ratio_w_h = w / h

            # 长截图处理 (如手机长截屏、聊天记录长图)
            if ratio_h_w > 1.8:
                target_w = min(w, 1080)
                target_h = int(h * (target_w / w))
                if target_h > 3840:
                    target_h = 3840
                    target_w = int(w * (target_h / h))
                im = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
            # 全景横图处理
            elif ratio_w_h > 1.8:
                target_h = min(h, 1080)
                target_w = int(w * (target_h / h))
                if target_w > 3840:
                    target_w = 3840
                    target_h = int(h * (target_w / w))
                im = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
            # 常规图片单边超 2048 缩放
            else:
                max_d = max(w, h)
                if max_d > 2048:
                    scale = 2048.0 / max_d
                    im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

            out_buf = io.BytesIO()
            im.save(out_buf, format="JPEG", quality=85, optimize=True)
            opt_bytes = out_buf.getvalue()
            return opt_bytes, "image/jpeg"
    except Exception as e:
        print(f"[-] PIL 图像优化失败 ({e})，使用原始二进制兜底")
        return raw_bytes, "image/jpeg"

async def fetch_image_as_base64(url: str, timeout: float = 20.0):
    clean_url = html.unescape(url).strip()
    if clean_url.startswith("data:image"):
        return clean_url

    local_path = clean_url
    if local_path.startswith("file:///"):
        local_path = local_path[8:]
    elif local_path.startswith("file://"):
        local_path = local_path[7:]

    if os.path.isfile(local_path):
        try:
            with open(local_path, "rb") as f:
                raw_data = f.read()
            opt_data, mime = optimize_image_for_llm(raw_data)
            b64_data = base64.b64encode(opt_data).decode("utf-8")
            return f"data:{mime};base64,{b64_data}"
        except Exception as e:
            print(f"[本地图片读取异常] {e}: {local_path}")
            return None

    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://qzone.qq.com/",
    }

    raw_bytes = None
    # 1. 优先使用 httpx 异步客户端下载
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=True) as http_client:
            resp = await http_client.get(clean_url, headers=headers)
            if resp.status_code == 200 and len(resp.content) > 0:
                raw_bytes = resp.content
            else:
                print(f"[httpx 下载返回状态码: {resp.status_code}]: {clean_url}")
    except Exception as e:
        print(f"[httpx 下载异常] {e}: {clean_url}，尝试 urllib 兜底...")

    # 2. urllib 兜底下载
    if raw_bytes is None:
        try:
            raw_bytes, _ = await asyncio.to_thread(_download_urllib, clean_url, timeout)
        except Exception as e:
            print(f"[urllib 兜底下载失败] {e}: {clean_url}")
            return None

    if not raw_bytes:
        return None

    # 3. 智能压缩与格式自适应
    opt_bytes, mime = optimize_image_for_llm(raw_bytes)
    b64_data = base64.b64encode(opt_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64_data}"
