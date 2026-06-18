"""Browser plugin — browser capability via Playwright."""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class BrowserPlugin(BasePlugin):
    spec = BridgeSpec(
        name="browser",
        version="0.1.0",
        capabilities=["browser"],
        description="Browser automation via Playwright",
    )
    plugin_spec = PluginSpec(
        name="browser",
        version="0.1.0",
        capabilities=["browser"],
        priority=10,
        description="Browser: open, click, fill, screenshot, scrape",
    )

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._page = None

    async def initialize(self) -> None:
        try:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)
            self._page = await self._browser.new_page()
            logger.info("browser plugin: Playwright Chromium launched")
        except Exception as e:
            logger.error(f"browser plugin init failed: {e}")
            logger.info("hint: run `playwright install chromium` once")

    def methods(self) -> list[str]:
        return ["open", "click", "fill", "screenshot", "scrape", "evaluate"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if not self._page:
            raise RuntimeError("browser plugin not initialized (run `playwright install chromium`)")
        if method == "open":
            return await self._open(**params)
        if method == "click":
            return await self._click(**params)
        if method == "fill":
            return await self._fill(**params)
        if method == "screenshot":
            return await self._screenshot(**params)
        if method == "scrape":
            return await self._scrape(**params)
        if method == "evaluate":
            return await self._evaluate(**params)
        raise ValueError(f"unknown method: {method}")

    async def _open(self, url: str) -> dict[str, Any]:
        resp = await self._page.goto(url)
        title = await self._page.title()
        return {"url": url, "title": title, "status": resp.status if resp else None}

    async def _click(self, selector: str) -> bool:
        await self._page.click(selector)
        return True

    async def _fill(self, selector: str, value: str) -> bool:
        await self._page.fill(selector, value)
        return True

    async def _screenshot(self, path: str = "/tmp/alterego-screenshot.png", full_page: bool = False) -> str:
        await self._page.screenshot(path=path, full_page=full_page)
        return path

    async def _scrape(self, selector: str = "body") -> dict[str, Any]:
        text = await self._page.inner_text(selector)
        return {"text": text[:5000], "truncated": len(text) > 5000}

    async def _evaluate(self, script: str) -> Any:
        return await self._page.evaluate(script)

    async def health(self) -> bool:
        return self._page is not None

    async def shutdown(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
