"""OpenAI 兼容 API Adapter。

统一处理所有兼容 OpenAI Chat API 的后端：
- Claude API（通过 meccy 代理）
- 本地 llama-server（Qwen 7B）
- Hermes Gateway
- 任何 OpenAI 兼容端点

所有后端的区别只是 endpoint + model + api_key。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from .base import AgentAdapter, AdapterConfig, AdapterResult

log = logging.getLogger("edict.adapter.openai")

# 默认端点映射（当 config.endpoint 未设置时）
_DEFAULT_ENDPOINTS = {
    "claude_api": "https://aiapi.meccy.top/v1/chat/completions",
    "local_llm": "http://localhost:8080/v1/chat/completions",
    "hermes": "http://localhost:9090/v1/chat/completions",
}

_DEFAULT_MODELS = {
    "claude_api": "claude-sonnet-4-6",
    "local_llm": "qwen2.5-7b-q4.gguf",
    "hermes": "deepseek-v4-flash",
}


class OpenAIAdapter(AgentAdapter):
    """兼容 OpenAI Chat API 的 LLM 适配器。"""

    async def run(
        self,
        agent_id: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> AdapterResult:
        endpoint = self._resolve_endpoint()
        model = self._resolve_model()

        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": f"你是 {agent_id}。请根据上下文执行你的职责。"},
                {"role": "user", "content": message},
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": 0.7,
        }

        log.info(f"[{agent_id}] → OpenAI adapter: {model} @ {endpoint}")

        try:
            start = time.monotonic()
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)

            elapsed = time.monotonic() - start
            log.info(f"[{agent_id}] ← {resp.status_code} in {elapsed:.1f}s")

            if resp.status_code != 200:
                return AdapterResult(
                    success=False,
                    stderr=f"HTTP {resp.status_code}: {resp.text[:500]}",
                    returncode=resp.status_code,
                    metadata={"endpoint": endpoint, "model": model, "elapsed_s": elapsed},
                )

            body = resp.json()
            content = (
                body.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            return AdapterResult(
                success=True,
                stdout=content or "",
                returncode=0,
                metadata={
                    "endpoint": endpoint,
                    "model": model,
                    "elapsed_s": elapsed,
                    "usage": body.get("usage", {}),
                },
            )

        except httpx.TimeoutException:
            return AdapterResult(
                success=False,
                stderr=f"Timeout after {self.config.timeout}s calling {endpoint}",
                returncode=-1,
            )
        except Exception as e:
            return AdapterResult(
                success=False,
                stderr=f"Error: {e}",
                returncode=-1,
            )

    async def health(self) -> bool:
        """轻量健康检查。"""
        endpoint = self._resolve_endpoint()
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                # 对大多数 OpenAI 兼容端点，发一个最小请求
                resp = await client.get(
                    endpoint.replace("/chat/completions", "/models"),
                    timeout=5,
                )
                return resp.status_code == 200
        except Exception:
            return False

    def _resolve_endpoint(self) -> str:
        if self.config.endpoint:
            return self.config.endpoint
        return _DEFAULT_ENDPOINTS.get(self.config.type, _DEFAULT_ENDPOINTS["local_llm"])

    def _resolve_model(self) -> str:
        if self.config.model:
            return self.config.model
        return _DEFAULT_MODELS.get(self.config.type, "qwen2.5-7b-q4.gguf")
