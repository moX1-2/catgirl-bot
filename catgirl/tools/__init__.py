# -*- coding: utf-8 -*-
"""
小橘 Agent 工具模块
"""

from .definitions import (
    TAVILY_TOOL_DEFINITION,
    DRAW_SVG_TOOL_DEFINITION,
    SEND_VOICE_TOOL_DEFINITION,
    GENERATE_IMAGE_TOOL_DEFINITION,
    WORKSPACE_RUN_TOOL_DEFINITION,
    WORKSPACE_WRITE_TOOL_DEFINITION,
    WORKSPACE_READ_TOOL_DEFINITION,
    WORKSPACE_LIST_TOOL_DEFINITION,
    FETCH_WEB_PAGE_TOOL_DEFINITION,
    SEARCH_MUSIC_CANDIDATES_TOOL_DEFINITION,
    PLAY_MUSIC_TOOL_DEFINITION
)
from .tavily import perform_tavily_search
from .svg import render_svg_to_png_base64
from .image import fetch_image_as_base64
from .tts import generate_speech, generate_speech_gemini, generate_speech_minimax
from .paint import generate_picture_gemini
from .fetch import fetch_web_page_content
from .music import search_and_download_music, search_candidates_tool

__all__ = [
    "TAVILY_TOOL_DEFINITION",
    "DRAW_SVG_TOOL_DEFINITION",
    "SEND_VOICE_TOOL_DEFINITION",
    "GENERATE_IMAGE_TOOL_DEFINITION",
    "perform_tavily_search",
    "render_svg_to_png_base64",
    "fetch_image_as_base64",
    "generate_speech",
    "generate_speech_gemini",
    "generate_speech_minimax",
    "generate_picture_gemini",
    "WORKSPACE_RUN_TOOL_DEFINITION",
    "WORKSPACE_WRITE_TOOL_DEFINITION",
    "WORKSPACE_READ_TOOL_DEFINITION",
    "WORKSPACE_LIST_TOOL_DEFINITION",
    "FETCH_WEB_PAGE_TOOL_DEFINITION",
    "fetch_web_page_content",
    "SEARCH_MUSIC_CANDIDATES_TOOL_DEFINITION",
    "PLAY_MUSIC_TOOL_DEFINITION",
    "search_and_download_music",
    "search_candidates_tool"
]
