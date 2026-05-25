"""Agent 适配器注册表。

管理 agent_id → Adapter 的路由映射。
从 agents.json 的 backend 配置自动初始化。
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any

from .base import AgentAdapter, AdapterConfig
from .openai_adapter import OpenAIAdapter
from .openclaw_adapter import OpenClawAdapter
from .claude_code_adapter import ClaudeCodeAdapter

log = logging.getLogger("edict.adapter.registry")

# 内置 adapter 类型映射
_BUILTIN_ADAPTERS: dict[str, type[AgentAdapter]] = {
    "openclaw": OpenClawAdapter,
    "openai": OpenAIAdapter,
    "claude_code": ClaudeCodeAdapter,
}

# 运行时注册表
_registry: dict[str, AgentAdapter] = {}


def register_adapter_type(name: str, cls: type[AgentAdapter]) -> None:
    """注册自定义 adapter 类型。"""
    _BUILTIN_ADAPTERS[name] = cls
    log.info(f"Registered adapter type: {name}")


async def get_adapter(agent_id: str) -> AgentAdapter | None:
    """获取 agent 对应的 adapter。"""
    return _registry.get(agent_id)


async def resolve_agent_backend(agent_id: str) -> str | None:
    """获取 agent 使用的后端类型（用于看板展示）。"""
    adapter = _registry.get(agent_id)
    if adapter:
        return adapter.config.type
    return None


async def init_registry(agents_json_path: str | pathlib.Path | None = None) -> int:
    """从 agents.json 初始化注册表。

    Returns:
        成功注册的 agent 数量
    """
    if agents_json_path is None:
        # 自动查找 agents.json
        candidates = [
            pathlib.Path(os.getcwd()) / "agents.json",
            pathlib.Path(__file__).resolve().parents[4] / "agents.json",
        ]
        for p in candidates:
            if p.exists():
                agents_json_path = p
                break

    if agents_json_path is None or not pathlib.Path(agents_json_path).exists():
        log.warning("agents.json not found, registry empty")
        return 0

    path = pathlib.Path(agents_json_path)

    try:
        agents = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.error(f"Failed to load {path}: {e}")
        return 0

    count = 0
    for agent_def in agents:
        agent_id = agent_def.get("id")
        if not agent_id:
            continue

        backend = agent_def.get("backend", {})
        adapter_type = backend.get("type", "openclaw")
        config = AdapterConfig.from_dict(backend)

        adapter_cls = _BUILTIN_ADAPTERS.get(adapter_type)
        if adapter_cls is None:
            log.warning(f"Unknown adapter type '{adapter_type}' for agent '{agent_id}', falling back to openclaw")
            adapter_cls = OpenClawAdapter
            config.type = "openclaw"

        try:
            adapter = adapter_cls(config)
            _registry[agent_id] = adapter
            count += 1
            log.info(f"  [{agent_id}] → {adapter}")
        except Exception as e:
            log.error(f"Failed to init adapter for '{agent_id}': {e}")

    log.info(f"Registry initialized: {count} agents")
    return count


def get_registry_snapshot() -> dict[str, str]:
    """获取注册表快照（用于看板展示）。"""
    return {
        agent_id: adapter.config.type
        for agent_id, adapter in _registry.items()
    }


async def clear_registry() -> None:
    """清空注册表（用于热重载）。"""
    _registry.clear()
    log.info("Registry cleared")
