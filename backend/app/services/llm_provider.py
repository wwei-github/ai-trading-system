"""LLM 服务抽象层。

提供统一的 LLM 调用接口，支持多 Provider：
- OpenAICompatibleProvider：OpenAI 兼容接口（支持字典初始化 + 环境变量向后兼容）
- OllamaProvider：Ollama 本地模型
- NoopProvider：无可用 Provider 时的降级响应

通过 ProviderFactory 工厂类管理 Provider 生命周期。
"""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger

from app.core.config import settings


class LLMProvider:
    """LLM 提供商抽象基类。"""

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """同步对话。"""
        raise NotImplementedError

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式对话（逐 token 生成）。"""
        raise NotImplementedError
        # pylint: disable=unreachable
        yield ""

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """生成文本向量嵌入。"""
        raise NotImplementedError


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容接口 Provider。

    支持从 config 字典初始化，也支持从环境变量加载（向后兼容）。
    支持任何兼容 OpenAI Chat Completions API 的服务，
    如 OpenAI、Azure OpenAI、Anthropic（兼容层）、本地 vLLM 等。
    """

    def __init__(self, config: Optional[dict] = None):
        if config is not None:
            self.api_key = config.get("api_key", "")
            self.base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")
            self.model = config.get("model", "gpt-4o-mini")
            self.embedding_model = config.get("embedding_model", "text-embedding-3-small")
            self.embedding_dimension = config.get("embedding_dimension", 1536)
            self.temperature = config.get("temperature", 0.7)
            self.max_tokens = config.get("max_tokens", 2000)
        else:
            # 从环境变量加载（向后兼容）
            self.api_key = settings.LLM_API_KEY
            self.base_url = settings.LLM_BASE_URL.rstrip("/")
            self.model = settings.LLM_MODEL
            self.embedding_model = settings.EMBEDDING_MODEL
            self.embedding_dimension = settings.EMBEDDING_DIMENSION
            self.temperature = settings.LLM_TEMPERATURE
            self.max_tokens = settings.LLM_MAX_TOKENS

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """同步对话。"""
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置，无法调用大语言模型")

        import httpx

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式对话（SSE）。"""
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置，无法调用大语言模型")

        import httpx

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """生成文本向量嵌入。"""
        if not self.api_key:
            # 降级：返回随机向量（仅供开发测试）
            import random

            return [
                [random.uniform(-1, 1) for _ in range(self.embedding_dimension)]
                for _ in texts
            ]

        import httpx

        payload = {
            "model": self.embedding_model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._get_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]


class OllamaProvider(LLMProvider):
    """Ollama 本地模型 Provider。

    API 对照：
    - Chat 端点：POST /api/chat（非 /v1/chat/completions）
    - 流式格式：每行独立 JSON { message: { content }, done: bool }
    - Embed 端点：POST /api/embed
    - 认证：无
    """

    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "http://ollama:11434").rstrip("/")
        self.model = config.get("model", "qwen3.5:7b")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 4096)
        self.embedding_model = config.get("embedding_model", "nomic-embed-text")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """同步对话。"""
        import httpx

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_predict": max_tokens or self.max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式对话（Ollama 流式格式）。"""
        import httpx

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_predict": max_tokens or self.max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done", False):
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """生成文本向量嵌入。"""
        import httpx

        payload = {"model": self.embedding_model, "input": texts}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self.base_url}/api/embed", json=payload)
            resp.raise_for_status()
            return resp.json().get("embeddings", [])


class NoopProvider(LLMProvider):
    """无可用 Provider 时的降级响应。

    当用户未配置任何 Provider 时，返回友好的提示消息。
    """

    def __init__(self, message: str = "当前未配置 AI Provider"):
        self._message = message

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        return f"【提示】{self._message}，请前往系统设置添加。"

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        yield f"【提示】{self._message}，请前往系统设置添加。"

    async def embed(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * 768 for _ in texts]


# 单例（已废弃，请使用 ProviderFactory 管理 Provider 生命周期）
_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """获取 LLM Provider 单例（已废弃，保留向后兼容）。

    请使用 ProviderFactory.get_active_provider(db) 替代。
    """
    global _provider
    if _provider is None:
        provider = settings.LLM_PROVIDER.lower()
        if provider in ("openai", "custom", "anthropic"):
            _provider = OpenAICompatibleProvider()
        else:
            _provider = OpenAICompatibleProvider()
    return _provider


__all__ = [
    "LLMProvider",
    "OpenAICompatibleProvider",
    "OllamaProvider",
    "NoopProvider",
    "get_llm_provider",
]