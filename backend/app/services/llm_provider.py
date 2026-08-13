"""LLM 服务抽象层。

提供统一的 LLM 调用接口，支持多 Provider（OpenAI 兼容接口）。
通过 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 配置切换。
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

    支持任何兼容 OpenAI Chat Completions API 的服务，
    如 OpenAI、Azure OpenAI、Anthropic（兼容层）、本地 vLLM 等。
    """

    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.model = settings.LLM_MODEL
        self.embedding_model = settings.EMBEDDING_MODEL
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
            return _mock_chat_response(messages)

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
            # 降级：模拟流式输出
            text = _mock_chat_response(messages)
            for word in text.split():
                yield word + " "
            return

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
                [random.uniform(-1, 1) for _ in range(settings.EMBEDDING_DIMENSION)]
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


def _mock_chat_response(messages: List[Dict[str, str]]) -> str:
    """未配置 LLM_API_KEY 时的降级响应。"""
    logger.warning("未配置 LLM_API_KEY，返回模拟响应")
    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = m.get("content", "")[:100]
            break
    return (
        "【模拟响应】当前未配置 LLM API Key，无法调用真实大语言模型。\n\n"
        f"您发送的消息：{user_msg}\n\n"
        "请在 .env 文件中配置 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL 后使用。"
    )


# 单例
_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """获取 LLM Provider 单例。"""
    global _provider
    if _provider is None:
        provider = settings.LLM_PROVIDER.lower()
        if provider in ("openai", "custom", "anthropic"):
            _provider = OpenAICompatibleProvider()
        else:
            _provider = OpenAICompatibleProvider()
    return _provider


__all__ = ["LLMProvider", "OpenAICompatibleProvider", "get_llm_provider"]
