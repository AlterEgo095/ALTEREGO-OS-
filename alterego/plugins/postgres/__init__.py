"""PostgreSQL plugin — database.sql capability."""
from __future__ import annotations

import os
from typing import Any

from loguru import logger

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class PostgresPlugin(BasePlugin):
    spec = BridgeSpec(
        name="postgres",
        version="0.1.0",
        capabilities=["database.sql"],
        description="PostgreSQL queries via asyncpg",
    )
    plugin_spec = PluginSpec(
        name="postgres",
        version="0.1.0",
        capabilities=["database.sql"],
        priority=10,
        description="PostgreSQL: query, execute, transaction",
    )

    def __init__(self) -> None:
        self._pool = None

    async def initialize(self) -> None:
        dsn = os.environ.get("POSTGRES_DSN")
        if not dsn:
            logger.warning("POSTGRES_DSN not set — postgres plugin will fail at first call")
            return
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(dsn)
            logger.info("postgres plugin: pool created")
        except Exception as e:
            logger.error(f"postgres plugin init failed: {e}")

    def methods(self) -> list[str]:
        return ["query", "execute", "transaction"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if not self._pool:
            raise RuntimeError("postgres plugin not connected (POSTGRES_DSN missing or invalid)")
        if method == "query":
            return await self._query(**params)
        if method == "execute":
            return await self._execute(**params)
        raise ValueError(f"unknown method: {method}")

    async def _query(self, sql: str, args: list | None = None) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *(args or []))
            return [dict(r) for r in rows]

    async def _execute(self, sql: str, args: list | None = None) -> str:
        async with self._pool.acquire() as conn:
            result = await conn.execute(sql, *(args or []))
            return result

    async def health(self) -> bool:
        return self._pool is not None

    async def shutdown(self) -> None:
        if self._pool:
            await self._pool.close()
