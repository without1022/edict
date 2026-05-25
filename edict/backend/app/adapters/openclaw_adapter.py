"""OpenClaw CLI Adapter。

调用 OpenClaw CLI 执行 agent 任务。
从 dispatch_worker.py 迁移过来的原有逻辑。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import tempfile
import time
from typing import Any

from ..config import get_settings
from .base import AgentAdapter, AdapterConfig, AdapterResult

log = logging.getLogger("edict.adapter.openclaw")


class OpenClawAdapter(AgentAdapter):
    """调用 OpenClaw CLI 的适配器（原有行为）。"""

    async def run(
        self,
        agent_id: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> AdapterResult:
        settings = get_settings()
        cmd = [
            settings.openclaw_bin,
            "agent",
            "--agent", agent_id,
            "-m", message,
        ]

        env = os.environ.copy()
        task_id = (context or {}).get("task_id", "")
        trace_id = (context or {}).get("trace_id", "")

        if task_id:
            env["EDICT_TASK_ID"] = task_id
        if trace_id:
            env["EDICT_TRACE_ID"] = trace_id
        env["EDICT_API_URL"] = f"http://localhost:{settings.port}"

        # 写入临时上下文文件
        context_file = None
        if context and task_id:
            try:
                context_data = {
                    "task_id": task_id,
                    "trace_id": trace_id,
                    "title": context.get("title", ""),
                    "description": context.get("description", ""),
                    "state": context.get("state", ""),
                    "org": context.get("org", ""),
                    "priority": context.get("priority", "中"),
                    "tags": context.get("tags", []),
                }
                fd, context_file = tempfile.mkstemp(
                    suffix=".json", prefix=f"edict_ctx_{task_id}_"
                )
                with os.fdopen(fd, "w") as f:
                    json.dump(context_data, f, ensure_ascii=False, indent=2)
                env["EDICT_CONTEXT_FILE"] = context_file
            except Exception as e:
                log.warning(f"Failed to write context file: {e}")

        log.info(f"[{agent_id}] → OpenClaw CLI: {' '.join(cmd)}")

        def _run() -> dict:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout,
                    env=env,
                    cwd=settings.openclaw_project_dir or None,
                )
                return {
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[-5000:] if proc.stdout else "",
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
                    "stderr": "openclaw command not found",
                }
            finally:
                if context_file:
                    try:
                        os.unlink(context_file)
                    except OSError:
                        pass

        loop = asyncio.get_event_loop()
        start = time.monotonic()
        result = await loop.run_in_executor(None, _run)
        elapsed = time.monotonic() - start

        success = result["returncode"] == 0
        log.info(
            f"[{agent_id}] ← OpenClaw CLI rc={result['returncode']} "
            f"in {elapsed:.1f}s"
        )

        return AdapterResult(
            success=success,
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            returncode=result["returncode"],
            metadata={"elapsed_s": elapsed},
        )

    async def health(self) -> bool:
        """检查 openclaw 二进制是否存在。"""
        settings = get_settings()
        try:
            proc = await asyncio.create_subprocess_exec(
                settings.openclaw_bin, "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            rc = await proc.wait()
            return rc == 0
        except FileNotFoundError:
            return False
