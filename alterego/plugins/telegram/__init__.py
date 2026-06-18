"""Telegram plugin — telegram capability via Bot API."""
from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class TelegramPlugin(BasePlugin):
    spec = BridgeSpec(
        name="telegram",
        version="0.1.0",
        capabilities=["telegram"],
        description="Telegram notifications via Bot API",
    )
    plugin_spec = PluginSpec(
        name="telegram",
        version="0.1.0",
        capabilities=["telegram"],
        priority=10,
        description="Telegram: send_message",
    )

    def __init__(self) -> None:
        self._token: str | None = None
        self._chat_id: str | None = None
        self._api_base: str = "https://api.telegram.org"

    async def initialize(self) -> None:
        self._token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self._chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not all([self._token, self._chat_id]):
            logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — telegram plugin disabled")

    def methods(self) -> list[str]:
        return ["send_message", "send_document"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if not self._token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
        chat_id = params.pop("chat_id", self._chat_id)
        if method == "send_message":
            return await self._send_message(chat_id=chat_id, **params)
        if method == "send_document":
            return await self._send_document(chat_id=chat_id, **params)
        raise ValueError(f"unknown method: {method}")

    async def _send_message(self, chat_id: str, text: str, parse_mode: str | None = None) -> dict[str, Any]:
        url = f"{self._api_base}/bot{self._token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return r.json()

    async def _send_document(self, chat_id: str, document_path: str) -> dict[str, Any]:
        url = f"{self._api_base}/bot{self._token}/sendDocument"
        async with httpx.AsyncClient() as client:
            with open(document_path, "rb") as f:
                r = await client.post(url, data={"chat_id": chat_id}, files={"document": f})
                r.raise_for_status()
                return r.json()

    async def health(self) -> bool:
        return all([self._token, self._chat_id])

    async def shutdown(self) -> None:
        pass
