"""LLM plugin — chat capabilities.

V1: uses OpenAI SDK directly (works for OpenAI API, Ollama via OpenAI-compat,
LiteLLM if installed). V2 will switch to LiteLLM routing.
"""
from __future__ import annotations

import os
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class LLMPlugin(BasePlugin):
    """LLM chat plugin. Connects to OpenAI or any OpenAI-compatible endpoint."""

    spec = BridgeSpec(
        name="llm",
        version="0.1.0",
        capabilities=["llm.chat"],
        description="LLM chat completion via OpenAI-compatible API",
    )
    plugin_spec = PluginSpec(
        name="llm",
        version="0.1.0",
        capabilities=["llm.chat"],
        priority=10,
        description="LLM chat (OpenAI/Ollama/LiteLLM)",
    )

    def __init__(self) -> None:
        self.client: AsyncOpenAI | None = None
        self.model: str = "gpt-4o-mini"

    async def initialize(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL")
        # If no OpenAI key, fall back to Ollama local
        if not api_key:
            ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            base_url = f"{ollama_url}/v1"
            api_key = "ollama"  # Ollama accepts any string
            self.model = os.environ.get("OLLAMA_MODEL", "llama3.2")
            logger.info(f"LLM plugin: using Ollama at {base_url} model={self.model}")
        else:
            self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            logger.info(f"LLM plugin: using OpenAI model={self.model}")

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def methods(self) -> list[str]:
        return ["chat", "embed"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if method == "chat":
            return await self._chat(**params)
        if method == "embed":
            return await self._embed(**params)
        raise ValueError(f"unknown method: {method}")

    async def _chat(
        self,
        user: str,
        system: str = "You are a helpful assistant.",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        assert self.client is not None, "LLM plugin not initialized"
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or ""
        return {
            "content": content,
            "model": resp.model,
            "usage": {
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            },
        }

    async def _embed(self, text: str, **kwargs: Any) -> list[float]:
        assert self.client is not None
        resp = await self.client.embeddings.create(
            model=kwargs.get("model", "text-embedding-3-small"),
            input=text,
        )
        return resp.data[0].embedding

    async def health(self) -> bool:
        return self.client is not None

    async def shutdown(self) -> None:
        # AsyncOpenAI has no explicit close needed
        pass
