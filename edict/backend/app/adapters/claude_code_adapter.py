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
            "--max-turns", str(self.config.extra.get("max_turns", 5)),
            "--print",
        ]

        # 如果配置了模型，加 --model 参数
        if self.config.model:
            cmd.extend(["--model", self.config.model])

        env = os.environ.copy()

        log.info(f"[{agent_id}] → Claude Code CLI: {claude_bin}")

        try:
            start = time.monotonic()
            # 通过 stdin 管道传递 prompt
            proc = await asyncio.create_subprocess_exec(
                claude_bin,
                "--print",
                "--max-turns", str(self.config.extra.get("max_turns", 5)),
                *(("--model", self.config.model) if self.config.model else ()),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy(),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=full_prompt.encode("utf-8")),
                timeout=self.config.timeout,
            )
            elapsed = time.monotonic() - start
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

            success = proc.returncode == 0
            log.info(
                f"[{agent_id}] ← Claude Code CLI rc={proc.returncode} "
                f"in {elapsed:.1f}s"
            )
            return AdapterResult(
                success=success,
                stdout=stdout[-10000:] if stdout else "",
                stderr=stderr[-2000:] if stderr else "",
                returncode=proc.returncode or 0,
                metadata={"elapsed_s": elapsed, "command": claude_bin},
            )

        except asyncio.TimeoutError:
            log.warning(f"[{agent_id}] ← Claude Code CLI TIMEOUT after {self.config.timeout}s")
            return AdapterResult(
                success=False,
                stderr=f"TIMEOUT after {self.config.timeout}s",
                returncode=-1,
            )
        except FileNotFoundError:
            log.error(f"[{agent_id}] ← Claude Code CLI not found: {claude_bin}")
            return AdapterResult(
                success=False,
                stderr=f"claude command not found: {claude_bin}",
                returncode=-1,
            )
        except Exception as e:
            log.error(f"[{agent_id}] ← Claude Code CLI error: {e}")
            return AdapterResult(
                success=False,
                stderr=f"Error: {e}",
                returncode=-1,
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
