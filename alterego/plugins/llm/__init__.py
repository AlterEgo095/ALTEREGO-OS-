"""LLM plugin — chat capabilities via pure HTTP (no SDK dependency).

Works with any OpenAI-compatible API:
  - OpenAI (https://api.openai.com/v1)
  - Ollama (http://localhost:11434/v1)
  - DeepSeek (https://api.deepseek.com/v1)
  - LiteLLM gateway (http://localhost:4000/v1)
  - Any OpenAI-compatible endpoint

Uses httpx only (already a dependency). No openai SDK needed.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class LLMPlugin(BasePlugin):
    """LLM chat plugin using pure httpx — no SDK dependency."""

    spec = BridgeSpec(
        name="llm",
        version="0.2.0",
        capabilities=["llm.chat"],
        description="LLM chat via OpenAI-compatible HTTP API (no SDK)",
    )
    plugin_spec = PluginSpec(
        name="llm",
        version="0.2.0",
        capabilities=["llm.chat"],
        priority=10,
        description="LLM chat (OpenAI/Ollama/DeepSeek/LiteLLM via httpx)",
    )

    def __init__(self) -> None:
        self._base_url: str = ""
        self._api_key: str = ""
        self._model: str = "gpt-4o-mini"
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        # Determine provider
        api_key = os.environ.get("OPENAI_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL", "")

        if api_key:
            # OpenAI or compatible
            self._base_url = base_url or "https://api.openai.com/v1"
            self._api_key = api_key
            self._model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            provider = "OpenAI" if "openai.com" in self._base_url else "custom"
        else:
            # Fall back to Ollama local
            ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            self._base_url = f"{ollama_url}/v1"
            self._api_key = "ollama"  # Ollama accepts any string
            self._model = os.environ.get("OLLAMA_MODEL", "llama3.2")
            provider = "Ollama"

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=180.0,  # 3 min — z-ai can take 30+ seconds per call
        )
        logger.info(f"LLM plugin: provider={provider} base_url={self._base_url} model={self._model}")

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
        """Send a chat completion request via HTTP."""
        if not self._client:
            raise RuntimeError("LLM plugin not initialized")

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            resp = await self._client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return {
                "content": content,
                "model": data.get("model", self._model),
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                },
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM HTTP error: {e.response.status_code} — {e.response.text[:200]}")
            raise RuntimeError(f"LLM API error {e.response.status_code}: {e.response.text[:200]}")
        except httpx.ConnectError as e:
            logger.error(f"LLM connection error: {e}")
            raise RuntimeError(f"Cannot connect to LLM at {self._base_url}. Is Ollama running? (ollama serve)")
        except Exception as e:
            logger.error(f"LLM error: {e}")
            raise

    async def _embed(self, text: str, **kwargs: Any) -> list[float]:
        if not self._client:
            raise RuntimeError("LLM plugin not initialized")
        payload = {
            "model": kwargs.get("model", "text-embedding-3-small"),
            "input": text,
        }
        resp = await self._client.post("/embeddings", json=payload)
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    async def health(self) -> bool:
        return self._client is not None

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
