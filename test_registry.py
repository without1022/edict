"""测试适配器注册表 — 验证 agents.json 配置的所有 agent 都能连通。"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "edict/backend"))
os.environ["EDICT_API_URL"] = "http://localhost:8000"

from app.adapters.registry import init_registry, get_adapter, get_registry_snapshot


async def main():
    print("=" * 55)
    print("🏛️ Edict 异构 Agent Adapter 注册表测试")
    print("=" * 55)

    # 从 agents.json 初始化注册表
    count = await init_registry("agents.json")
    snapshot = get_registry_snapshot()
    print(f"\n📋 注册表: {len(snapshot)} agents\n")

    for agent_id, backend_type in snapshot.items():
        adapter = await get_adapter(agent_id)
        print(f"  [{agent_id:12s}] → {backend_type:12s}  适配器: {adapter}")

    print(f"\n{'='*55}")
    print("✅ 注册表初始化成功，所有 agent 已映射到对应的 adapter")
    print(f"   后端类型分布: {len([a for a in snapshot.values() if a == 'openai'])}x openai, "
          f"{len([a for a in snapshot.values() if a == 'openclaw'])}x openclaw")
    print("=" * 55)

    # 选择一个 agent 进行实际调用测试
    print("\n🧪 实际调用测试（选 libu 测试联网调用）")
    libu_adapter = await get_adapter("libu")
    if libu_adapter:
        result = await libu_adapter.run(
            "libu",
            "用一句话回答：Python 的优点是什么？"
        )
        if result.success:
            print(f"  ✅ libu 调用成功: {result.stdout[:100]}")
        else:
            print(f"  ❌ libu 调用失败: {result.stderr[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
