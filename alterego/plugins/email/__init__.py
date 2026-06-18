"""Email plugin — email capability via SMTP."""
from __future__ import annotations

import os
from email.message import EmailMessage
from typing import Any

from loguru import logger

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class EmailPlugin(BasePlugin):
    spec = BridgeSpec(
        name="email",
        version="0.1.0",
        capabilities=["email"],
        description="Send email via SMTP",
    )
    plugin_spec = PluginSpec(
        name="email",
        version="0.1.0",
        capabilities=["email"],
        priority=10,
        description="Email: send via SMTP",
    )

    def __init__(self) -> None:
        self._host: str | None = None
        self._port: int = 587
        self._user: str | None = None
        self._password: str | None = None
        self._from: str | None = None

    async def initialize(self) -> None:
        self._host = os.environ.get("SMTP_HOST")
        self._port = int(os.environ.get("SMTP_PORT", "587"))
        self._user = os.environ.get("SMTP_USER")
        self._password = os.environ.get("SMTP_PASSWORD")
        self._from = os.environ.get("SMTP_FROM", self._user)
        if not all([self._host, self._user, self._password]):
            logger.warning("SMTP_* env vars incomplete — email plugin will fail at first call")

    def methods(self) -> list[str]:
        return ["send"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if method == "send":
            return await self._send(**params)
        raise ValueError(f"unknown method: {method}")

    async def _send(self, to: str, subject: str, body: str, html: bool = False) -> dict[str, Any]:
        if not all([self._host, self._user, self._password, self._from]):
            raise RuntimeError("SMTP not configured")
        import aiosmtplib
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = to
        msg["Subject"] = subject
        if html:
            msg.add_alternative(body, subtype="html")
        else:
            msg.set_content(body)
        await aiosmtplib.send(
            msg,
            hostname=self._host,
            port=self._port,
            username=self._user,
            password=self._password,
            start_tls=True,
        )
        return {"to": to, "subject": subject, "sent": True}

    async def health(self) -> bool:
        return all([self._host, self._user, self._password])

    async def shutdown(self) -> None:
        pass
