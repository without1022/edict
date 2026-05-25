"""Agent Adapter 抽象接口。

每个 Agent 后端实现此接口，dispatch_worker 通过注册表路由调用。
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("edict.adapter")


@dataclass
class AdapterResult:
    """Adapter 执行结果。"""
    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterConfig:
    """Adapter 配置，从 agents.json 的 backend.config 解析。"""
    type: str
    endpoint: str | None = None
    model: str | None = None
    api_key: str | None = None
    max_tokens: int = 4096
    timeout: int = 300
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> AdapterConfig:
        return cls(
            type=d.get("type", "openclaw"),
            endpoint=d.get("endpoint"),
            model=d.get("model"),
            api_key=d.get("api_key"),
            max_tokens=d.get("max_tokens", 4096),
            timeout=d.get("timeout", 300),
            extra=d.get("extra", {}),
        )


class AgentAdapter(abc.ABC):
    """Agent 后端适配器基类。

    所有适配器必须实现 run() 方法。
    """

    def __init__(self, config: AdapterConfig):
        self.config = config

    @abc.abstractmethod
    async def run(
        self,
        agent_id: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> AdapterResult:
        """执行 Agent 调用。

        Args:
            agent_id: Agent ID（如 hubu, libu）
            message: 组装好的完整 prompt
            context: 额外上下文（task_id, trace_id 等）

        Returns:
            AdapterResult
        """
        ...

    async def health(self) -> bool:
        """健康检查（可选重写）。"""
        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.config.type})"
