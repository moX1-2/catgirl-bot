# -*- coding: utf-8 -*-
"""
SVG 绘图与 Linux 高清渲染工具
优先使用 rsvg-convert (配合中文字体)，cairosvg 作为备选
"""

import re
import base64
import subprocess

def render_svg_to_png_base64(svg_str: str) -> tuple:
    """
    将 SVG XML 代码在 Linux 环境下渲染为高清 PNG 图片 Base64
    优先使用 rsvg-convert (配合文泉驿微米黑中文字体)，cairosvg 作为备选
    """
    clean_svg = svg_str.strip()
    clean_svg = re.sub(r"^`{3}(?:xml|svg)?\s*", "", clean_svg, flags=re.I)
    clean_svg = re.sub(r"\s*`{3}$", "", clean_svg)
    if "xmlns=" not in clean_svg:
        clean_svg = clean_svg.replace("<svg", "<svg xmlns='http://www.w3.org/2000/svg'", 1)

    svg_bytes = clean_svg.encode("utf-8")
    try:
        proc = subprocess.run(["rsvg-convert", "-f", "png"], input=svg_bytes, capture_output=True, timeout=8.0)
        if proc.returncode == 0 and len(proc.stdout) > 0:
            b64 = base64.b64encode(proc.stdout).decode("utf-8")
            return b64, ""
    except Exception as e:
        print(f"[-] rsvg-convert 渲染异常: {e}")

    try:
        import cairosvg
        png_data = cairosvg.svg2png(bytestring=svg_bytes)
        if png_data and len(png_data) > 0:
            b64 = base64.b64encode(png_data).decode("utf-8")
            return b64, ""
    except Exception as e:
        print(f"[-] cairosvg 渲染异常: {e}")
        return "", f"SVG 渲染引擎报错: {e}"

    return "", "SVG 渲染未输出有效图像数据"
