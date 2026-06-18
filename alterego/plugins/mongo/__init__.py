"""MongoDB plugin — database.nosql capability."""
from __future__ import annotations

import os
from typing import Any

from loguru import logger

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class MongoPlugin(BasePlugin):
    spec = BridgeSpec(
        name="mongo",
        version="0.1.0",
        capabilities=["database.nosql"],
        description="MongoDB queries via motor (async)",
    )
    plugin_spec = PluginSpec(
        name="mongo",
        version="0.1.0",
        capabilities=["database.nosql"],
        priority=10,
        description="MongoDB: find, insert, update, aggregate",
    )

    def __init__(self) -> None:
        self._client = None
        self._db = None

    async def initialize(self) -> None:
        uri = os.environ.get("MONGO_URI")
        if not uri:
            logger.warning("MONGO_URI not set — mongo plugin will fail at first call")
            return
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            self._client = AsyncIOMotorClient(uri)
            db_name = os.environ.get("MONGO_DB", "alterego")
            self._db = self._client[db_name]
            await self._client.admin.command("ping")
            logger.info(f"mongo plugin: connected to db '{db_name}'")
        except Exception as e:
            logger.error(f"mongo plugin init failed: {e}")

    def methods(self) -> list[str]:
        return ["find", "find_one", "insert", "update", "delete", "count"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if not self._db:
            raise RuntimeError("mongo plugin not connected")
        collection = params.pop("collection")
        col = self._db[collection]
        if method == "find":
            cursor = col.find(params.get("filter", {}))
            if "limit" in params:
                cursor = cursor.limit(params["limit"])
            return [doc async for doc in cursor]
        if method == "find_one":
            doc = await col.find_one(params.get("filter", {}))
            return doc
        if method == "insert":
            result = await col.insert_one(params.get("document", {}))
            return {"inserted_id": str(result.inserted_id)}
        if method == "update":
            result = await col.update_many(
                params.get("filter", {}),
                params.get("update", {"$set": params.get("set", {})}),
            )
            return {"matched": result.matched_count, "modified": result.modified_count}
        if method == "delete":
            result = await col.delete_many(params.get("filter", {}))
            return {"deleted": result.deleted_count}
        if method == "count":
            return await col.count_documents(params.get("filter", {}))
        raise ValueError(f"unknown method: {method}")

    async def health(self) -> bool:
        return self._client is not None

    async def shutdown(self) -> None:
        if self._client:
            self._client.close()
