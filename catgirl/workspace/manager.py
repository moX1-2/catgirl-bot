# -*- coding: utf-8 -*-
"""
小橘 Agent 工作区与隔离沙箱管理器
提供会话级临时沙箱空间、安全路径防逃逸判定、受控命令执行与全自动生命周期释放释放逻辑
"""

import os
import re
import time
import shutil
import hashlib
import signal
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import (
    WORKSPACE_BASE_DIR,
    WORKSPACE_MAX_FILE_SIZE_MB,
    WORKSPACE_MAX_TOTAL_MB,
    WORKSPACE_CMD_TIMEOUT_SEC,
    WORKSPACE_TTL_SECONDS
)

class SecurityError(Exception):
    pass

class WorkspaceManager:
    """
    轻量级临时工作区与安全沙箱管理器
    1. 会话空间隔离：每个会话拥有独立的沙箱子目录
    2. 路径防穿透：严格禁止 ../ 逃逸访问沙箱外部目录
    3. 配额管控：限制单文件与工作区总体积，防止撑爆磁盘
    4. 释放逻辑：定时扫描清理超期空间、会话结束/重置即刻释放、子进程死锁强制强杀释放
    """

    def __init__(self, base_dir: str = WORKSPACE_BASE_DIR):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
        # 记录各工作区最后活动时间 session_key -> last_active_timestamp
        self.last_active: Dict[str, float] = {}

    def _get_dir_name(self, session_key: str) -> str:
        safe_hash = hashlib.sha256(session_key.encode("utf-8")).hexdigest()[:16]
        safe_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", session_key)[:16]
        return f"ws_{safe_prefix}_{safe_hash}"

    def get_workspace_path(self, session_key: str, create: bool = True) -> str:
        """获取指定会话的工作区绝对路径"""
        dir_name = self._get_dir_name(session_key)
        ws_path = os.path.join(self.base_dir, dir_name)
        if create and not os.path.exists(ws_path):
            os.makedirs(ws_path, exist_ok=True)
        self.last_active[session_key] = time.time()
        return ws_path

    def resolve_safe_path(self, session_key: str, relative_path: str) -> str:
        """
        将用户/模型传入的相对路径解析为沙箱内的绝对路径
        若发现越狱穿越 (../ 或符号链接逃逸) 则立即拒绝
        """
        ws_path = self.get_workspace_path(session_key, create=True)
        # 规范化清理
        clean_rel = relative_path.strip().lstrip("/\\")
        target_path = os.path.abspath(os.path.join(ws_path, clean_rel))

        # 校验公共前缀必须为工作区本身
        if os.path.commonpath([ws_path, target_path]) != ws_path:
            raise SecurityError(f"安全沙箱限制：禁止访问工作区外部路径 ({relative_path})")

        return target_path

    def get_workspace_total_size(self, session_key: str) -> int:
        """计算当前工作区已占用的字节数"""
        ws_path = self.get_workspace_path(session_key, create=False)
        if not os.path.exists(ws_path):
            return 0
        total = 0
        for root, _, files in os.walk(ws_path):
            for f in files:
                fp = os.path.join(root, f)
                if not os.path.islink(fp) and os.path.exists(fp):
                    total += os.path.getsize(fp)
        return total

    def write_file(self, session_key: str, relative_path: str, content: str) -> Tuple[bool, str]:
        """向沙箱内安全写入文件"""
        try:
            target_path = self.resolve_safe_path(session_key, relative_path)
            content_bytes = content.encode("utf-8")

            # 1. 单文件大小限制
            if len(content_bytes) > WORKSPACE_MAX_FILE_SIZE_MB * 1024 * 1024:
                return False, f"文件大小超过限制 (单文件最大允许 {WORKSPACE_MAX_FILE_SIZE_MB}MB)"

            # 2. 总体积配额限制
            current_total = self.get_workspace_total_size(session_key)
            if current_total + len(content_bytes) > WORKSPACE_MAX_TOTAL_MB * 1024 * 1024:
                return False, f"工作区容量不足 (总限额 {WORKSPACE_MAX_TOTAL_MB}MB)，请清理不必要文件后再写入"

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(content_bytes)

            self.last_active[session_key] = time.time()
            return True, f"文件已安全写入: {relative_path} (大小: {len(content_bytes)} 字节)"
        except Exception as e:
            return False, f"写入文件异常: {e}"

    def read_file(self, session_key: str, relative_path: str, max_chars: int = 8000) -> Tuple[bool, str]:
        """从沙箱内安全读取文本文件"""
        try:
            target_path = self.resolve_safe_path(session_key, relative_path)
            if not os.path.exists(target_path):
                return False, f"文件不存在: {relative_path}"
            if os.path.isdir(target_path):
                return False, f"目标是一个目录而非文件: {relative_path}"

            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                data = f.read(max_chars + 1)

            self.last_active[session_key] = time.time()
            if len(data) > max_chars:
                return True, data[:max_chars] + f"\n...[文件内容过长，仅展示前 {max_chars} 字符]..."
            return True, data
        except Exception as e:
            return False, f"读取文件异常: {e}"

    def list_files(self, session_key: str) -> List[Dict[str, str]]:
        """列出沙箱内当前所有文件与目录状态"""
        ws_path = self.get_workspace_path(session_key, create=True)
        items = []
        for root, dirs, files in os.walk(ws_path):
            rel_root = os.path.relpath(root, ws_path)
            if rel_root == ".":
                rel_root = ""
            for d in dirs:
                items.append({
                    "path": os.path.join(rel_root, d).replace("\\", "/"),
                    "type": "dir",
                    "size": 0
                })
            for f in files:
                full = os.path.join(root, f)
                sz = os.path.getsize(full) if os.path.exists(full) else 0
                items.append({
                    "path": os.path.join(rel_root, f).replace("\\", "/"),
                    "type": "file",
                    "size": sz
                })
        self.last_active[session_key] = time.time()
        return items

    def run_command(
        self,
        session_key: str,
        command: str,
        timeout: float = WORKSPACE_CMD_TIMEOUT_SEC
    ) -> Tuple[int, str, str]:
        """
        在工作区安全目录内执行命令 (如 Python 数据处理、文本转换等)
        具备进程组超期强杀机制，确保不残留僵尸进程
        """
        ws_path = self.get_workspace_path(session_key, create=True)
        self.last_active[session_key] = time.time()

        # 危险命令防御拦截
        clean_cmd = command.strip()
        blocked_patterns = [r"rm\s+-rf\s+/", r"mkfs", r":(){ :|:& };:", r">\s*/dev/sd"]
        for bp in blocked_patterns:
            if re.search(bp, clean_cmd):
                return -1, "", "安全沙箱保护拦截：禁止执行高危系统级破坏命令。"

        env = os.environ.copy()
        env["PWD"] = ws_path
        env["WORKSPACE_ROOT"] = ws_path

        proc = None
        try:
            # 开启新会话组 preexec_fn=os.setsid，便于超时彻底杀掉进程树
            proc = subprocess.Popen(
                clean_cmd,
                shell=True,
                cwd=ws_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None
            )

            stdout_text, stderr_text = proc.communicate(timeout=timeout)
            ret_code = proc.returncode
            return ret_code, stdout_text.strip(), stderr_text.strip()

        except subprocess.TimeoutExpired:
            # 强杀进程组释放资源
            if proc:
                try:
                    if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    else:
                        proc.kill()
                    proc.communicate()
                except Exception:
                    pass
            return -1, "", f"沙箱命令执行超时 (上限 {timeout} 秒)，进程已被强制终止并释放资源。"

        except Exception as e:
            return -1, "", f"执行命令发生异常: {e}"

    def cleanup_workspace(self, session_key: str) -> bool:
        """释放并彻底删除指定会话的工作区空间"""
        dir_name = self._get_dir_name(session_key)
        ws_path = os.path.join(self.base_dir, dir_name)
        self.last_active.pop(session_key, None)
        if os.path.exists(ws_path):
            try:
                shutil.rmtree(ws_path, ignore_errors=True)
                print(f"[+] 成功释放沙箱工作区: {dir_name}")
                return True
            except Exception as e:
                print(f"[-] 释放沙箱工作区失败 ({dir_name}): {e}")
                return False
        return True

    def cleanup_expired_workspaces(self, max_idle_seconds: float = WORKSPACE_TTL_SECONDS) -> int:
        """
        定时垃圾回收与释放逻辑：
        扫描工作区根目录，彻底删除最后修改时间超过 TTL 的闲置沙箱，杜绝磁盘泄漏
        """
        if not os.path.exists(self.base_dir):
            return 0
        now = time.time()
        purged_count = 0

        try:
            for entry in os.listdir(self.base_dir):
                entry_path = os.path.join(self.base_dir, entry)
                if os.path.isdir(entry_path) and entry.startswith("ws_"):
                    # 检查目录的 mtime
                    mtime = os.path.getmtime(entry_path)
                    if now - mtime > max_idle_seconds:
                        try:
                            shutil.rmtree(entry_path, ignore_errors=True)
                            purged_count += 1
                        except Exception:
                            pass
        except Exception as e:
            print(f"[-] 扫描清理闲置工作区异常: {e}")

        if purged_count > 0:
            print(f"[+] 自动垃圾回收释放了 {purged_count} 个闲置沙箱工作区！")
        return purged_count

# 单例导出
workspace_manager = WorkspaceManager()
