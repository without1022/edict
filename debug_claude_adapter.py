"""调试 Claude Code adapter - 测试 asyncio 路径"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "edict/backend"))
os.environ["EDICT_API_URL"] = "http://localhost:8000"

from app.adapters.base import AdapterConfig
from app.adapters.claude_code_adapter import ClaudeCodeAdapter


async def main():
    adapter = ClaudeCodeAdapter(AdapterConfig(
        type="claude_code",
        endpoint="claude-meccy",
        model="sonnet",
        max_tokens=200,
        timeout=30,
        extra={"max_turns": 1, "task_type": "coding"},
    ))
    
    # 先测试子进程直接
    loop = asyncio.get_event_loop()
    import subprocess, time
    
    def _direct():
        env = os.environ.copy()
        cmd = ["claude-meccy", "-p", "hi", "--max-turns", "1", "--print"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        return proc.returncode, proc.stdout[:100]
    
    print("直接 subprocess...")
    start = time.time()
    rc, out = await loop.run_in_executor(None, _direct)
    print(f"  ✅ rc={rc} elapsed={time.time()-start:.1f}s")
    print(f"  out={out}")
    
    # 再测试 adapter
    print("\nadapter.run...")
    result = await adapter.run("hubu", "用一句话回复：Python的列表推导式是什么？")
    print(f"  success={result.success} rc={result.returncode}")
    print(f"  stdout={result.stdout[:200]}")
    print(f"  stderr={result.stderr[:200]}")


asyncio.run(main())
