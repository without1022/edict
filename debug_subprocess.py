"""调试 - 精确定位 subprocess 失败原因"""
import subprocess
import os
import sys
import time

# 测试1: 从文件运行 - 基础 subprocess
print("=== 测试1: 基础 subprocess.run (非async) ===")
env = os.environ.copy()
cmd = ["claude-meccy", "-p", "hi", "--max-turns", "1"]
start = time.time()
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
print(f"  ✅ rc={proc.returncode} elapsed={time.time()-start:.1f}s")
print(f"  out={proc.stdout[:100]}")

# 测试2: 从线程运行
print("\n=== 测试2: 在线程中运行 ===")
import threading

def thread_run():
    env = os.environ.copy()
    cmd = ["claude-meccy", "-p", "hi", "--max-turns", "1"]
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
    print(f"  ✅ rc={proc.returncode} elapsed={time.time()-start:.1f}s")
    print(f"  out={proc.stdout[:100]}")

t = threading.Thread(target=thread_run)
t.start()
t.join()

# 测试3: 有大量已有claude进程时运行
print("\n=== 测试3: 杀掉已有claude进程后运行 ===")
os.system("pkill -f 'claude --output-format' 2>/dev/null || true")
time.sleep(1)

start = time.time()
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
print(f"  ✅ rc={proc.returncode} elapsed={time.time()-start:.1f}s")
print(f"  out={proc.stdout[:100]}")
