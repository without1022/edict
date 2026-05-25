"""测试所有 Agent Adapter 是否能正常调用。"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "edict/backend"))
os.environ["EDICT_API_URL"] = "http://localhost:8000"

from app.adapters.base import AdapterConfig
from app.adapters.openai_adapter import OpenAIAdapter

MECCY_KEY = ""
DEEPSEEK_KEY = ""
env_file = os.path.expanduser("~/.hermes/.env")
if os.path.exists(env_file):
    for line in open(env_file):
        if line.startswith("MECCY_API_KEY="):
            MECCY_KEY = line.strip().split("=", 1)[1]
        if line.startswith("DEEPSEEK_API_KEY="):
            DEEPSEEK_KEY = line.strip().split("=", 1)[1]

TESTS = [
    {
        "name": "本地 Qwen 7B (taizi/zaochao)",
        "adapter": OpenAIAdapter(AdapterConfig(
            type="local_llm",
            endpoint="http://localhost:8080/v1/chat/completions",
            model="qwen2.5-7b-q4.gguf",
            max_tokens=100, timeout=30,
        )),
        "message": "用户说：帮我看看这个项目\n请判断这是闲聊还是正式旨意？",
    },
    {
        "name": "DeepSeek V4 Flash (zhongshu/menxia/六部)",
        "adapter": OpenAIAdapter(AdapterConfig(
            type="deepseek_api",
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-flash",
            api_key=DEEPSEEK_KEY,
            max_tokens=200, timeout=60,
        )),
        "message": "用一句话说明：什么是三省六部制度？",
    },
    {
        "name": "DeepSeek V4 Pro (xingbu/审查)",
        "adapter": OpenAIAdapter(AdapterConfig(
            type="deepseek_api",
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-pro",
            api_key=DEEPSEEK_KEY,
            max_tokens=200, timeout=60,
        )),
        "message": "审查这段代码的风险：print(exec(input()))",
    },
]

async def run_test(test):
    name = test["name"]
    adapter = test["adapter"]
    print(f"\n{'='*50}\n🧪 {name}\n  适配器: {adapter}\n{'='*50}")
    print("  调用中...", end=" ", flush=True)
    try:
        result = await adapter.run("test", test["message"])
        if result.success:
            print(f"✅ 成功 (rc={result.returncode})")
            print(f"  输出: {result.stdout[:200]}")
            if result.metadata.get("elapsed_s"):
                print(f"  耗时: {result.metadata['elapsed_s']:.1f}s")
            return True
        else:
            print(f"❌ 失败: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False

async def main():
    print("=" * 50)
    print(f"🏛️ Adapter 连通性测试 (DEEPSEEK_KEY={'已加载' if DEEPSEEK_KEY else '❌未找到'})")
    print(f"   测试数: {len(TESTS)}")
    print("=" * 50)
    results = [await run_test(t) for t in TESTS]
    passed = sum(results)
    print(f"\n📊 通过: {passed}/{len(results)}")

asyncio.run(main())
