"""Claude Code CLI Adapter。

调用 claude-meccy（或原版 claude）执行编码/执行任务。
走 subprocess + PTY 模式，适用于代码生成、重构、审查。
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import time
from typing import Any

from .base import AgentAdapter, AdapterConfig, AdapterResult

log = logging.getLogger("edict.adapter.claude_code")

# 任务类型提示映射
_TASK_HINTS = {
    "coding": """
你正在作为编码 agent 执行任务。
规则：
1. 先理解需求，然后实现
2. 如果需要在当前目录操作，使用 bash 工具
3. 完成后输出执行摘要
4. 如果遇到问题，输出错误信息
""",
    "review": """
你正在作为代码审查 agent。
审查重点：
1. 功能正确性
2. 代码质量
3. 安全性
4. 性能
输出审查结论和修改建议。
""",
    "research": """
你正在作为调研 agent。
要求：
1. 搜索相关信息
2. 整理要点
3. 给出结论或建议
""",
}


class ClaudeCodeAdapter(AgentAdapter):
    """Claude Code CLI 适配器（通过 claude-meccy 包装器）。"""

    async def run(
        self,
        agent_id: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> AdapterResult:
        claude_bin = self.config.endpoint or "claude-meccy"
        task_type = (context or {}).get("task_type", "coding")
        hint = _TASK_HINTS.get(task_type, "")

        # 组装 prompt：系统提示 + 任务 + 上下文
        prompt_parts = [hint, f"## 任务\n{message}"]
        if context:
            task_id = context.get("task_id", "")
            if task_id:
                prompt_parts.append(f"\n## 任务信息\nID: {task_id}")
            title = context.get("title", "")
            if title:
                prompt_parts.append(f"标题: {title}")

        full_prompt = "\n\n".join(prompt_parts)

        log.info(f"[{agent_id}] → Claude Code CLI: {claude_bin}")

        cmd = [
            claude_bin,
            "-p", full_prompt,
            "--max-turns", str(self.config.extra.get("max_turns", 15)),
        ]

        # 如果配置了模型，加 --model 参数
        if self.config.model:
            cmd.extend(["--model", self.config.model])

        env = os.environ.copy()

        def _run() -> dict:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout,
                    env=env,
                )
                return {
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[-10000:] if proc.stdout else "",
                    "stderr": proc.stderr[-2000:] if proc.stderr else "",
                }
            except subprocess.TimeoutExpired:
                return {
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"TIMEOUT after {self.config.timeout}s",
                }
            except FileNotFoundError:
                return {
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"claude command not found: {claude_bin}",
                }

        loop = asyncio.get_event_loop()
        start = time.monotonic()
        result = await loop.run_in_executor(None, _run)
        elapsed = time.monotonic() - start

        success = result["returncode"] == 0
        log.info(
            f"[{agent_id}] ← Claude Code CLI rc={result['returncode']} "
            f"in {elapsed:.1f}s"
        )

        return AdapterResult(
            success=success,
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            returncode=result["returncode"],
            metadata={"elapsed_s": elapsed, "command": claude_bin},
        )

    async def health(self) -> bool:
        """检查 claude CLI 是否可用。"""
        claude_bin = self.config.endpoint or "claude-meccy"
        try:
            proc = await asyncio.create_subprocess_exec(
                claude_bin, "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            rc = await proc.wait()
            return rc == 0
        except FileNotFoundError:
            return False
