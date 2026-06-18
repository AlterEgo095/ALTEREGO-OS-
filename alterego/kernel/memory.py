"""ALTEREGO OS — Memory (V1: SQLite).

Centralized memory with 10 entity types. V2 will swap to PostgreSQL.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel

# 10 V1 entity types
ENTITY_TYPES = [
    "projects",
    "repositories",
    "servers",
    "containers",
    "users",
    "conversations",
    "tasks",
    "documents",
    "preferences",
    "knowledge",
]


class MemoryRecord(BaseModel):
    id: str
    entity_type: str
    data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class Memory:
    """Abstract memory protocol. V1: SQLite. V2: PostgreSQL."""

    async def put(self, entity_type: str, data: dict[str, Any], id: Optional[str] = None) -> str:
        raise NotImplementedError

    async def get(self, entity_type: str, id: str) -> Optional[MemoryRecord]:
        raise NotImplementedError

    async def query(self, entity_type: str, **filters: Any) -> list[MemoryRecord]:
        raise NotImplementedError

    async def update(self, entity_type: str, id: str, data: dict[str, Any]) -> bool:
        raise NotImplementedError

    async def delete(self, entity_type: str, id: str) -> bool:
        raise NotImplementedError


class SQLiteMemory(Memory):
    """V1 SQLite memory. Single-file, no external service required."""

    def __init__(self, db_path: str | Path = "./data/alterego.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database with corruption recovery.

        If the DB file is corrupted (e.g. binary garbage), SQLite will raise
        DatabaseError. We catch it, backup the corrupted file, and recreate
        a fresh schema — losing the data but keeping the system running.
        """
        try:
            self._try_open_or_create()
        except sqlite3.DatabaseError as e:
            logger.warning(f"memory DB appears corrupted ({e}); backing up and recreating")
            backup_path = self.db_path.with_suffix(f".corrupted.{int(datetime.utcnow().timestamp())}.db")
            try:
                self.db_path.rename(backup_path)
                logger.info(f"corrupted DB backed up to {backup_path}")
            except OSError as rename_err:
                logger.error(f"could not backup corrupted DB: {rename_err}")
                # As a last resort, delete it
                try:
                    self.db_path.unlink()
                except OSError:
                    pass
            # Recreate fresh
            self._try_open_or_create()
            logger.info("memory DB recreated with fresh schema")
        logger.debug(f"memory initialized at {self.db_path}")

    def _try_open_or_create(self) -> None:
        """Open the DB and ensure schema exists. Raises sqlite3.DatabaseError on corruption."""
        with sqlite3.connect(self.db_path) as conn:
            # Quick integrity check
            try:
                conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
            except sqlite3.DatabaseError:
                raise  # let _init_db handle it
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    data TEXT NOT NULL,  -- JSON
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_entity ON memory(entity_type)"
            )
            conn.commit()

    async def put(self, entity_type: str, data: dict[str, Any], id: Optional[str] = None) -> str:
        if entity_type not in ENTITY_TYPES:
            raise ValueError(
                f"Unknown entity_type '{entity_type}'. Allowed: {ENTITY_TYPES}"
            )
        if id is None:
            id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory (id, entity_type, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (id, entity_type, json.dumps(data, default=str), now, now),
            )
            conn.commit()
        logger.debug(f"memory.put({entity_type}, {id})")
        return id

    async def get(self, entity_type: str, id: str) -> Optional[MemoryRecord]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, entity_type, data, created_at, updated_at FROM memory "
                "WHERE entity_type = ? AND id = ?",
                (entity_type, id),
            ).fetchone()
        if not row:
            return None
        return MemoryRecord(
            id=row[0],
            entity_type=row[1],
            data=json.loads(row[2]),
            created_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
        )

    async def query(self, entity_type: str, **filters: Any) -> list[MemoryRecord]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, entity_type, data, created_at, updated_at FROM memory "
                "WHERE entity_type = ?",
                (entity_type,),
            ).fetchall()
        records = []
        for row in rows:
            rec = MemoryRecord(
                id=row[0],
                entity_type=row[1],
                data=json.loads(row[2]),
                created_at=datetime.fromisoformat(row[3]),
                updated_at=datetime.fromisoformat(row[4]),
            )
            # Apply filters (simple equality on top-level keys)
            if all(rec.data.get(k) == v for k, v in filters.items()):
                records.append(rec)
        return records

    async def update(self, entity_type: str, id: str, data: dict[str, Any]) -> bool:
        existing = await self.get(entity_type, id)
        if not existing:
            return False
        merged = {**existing.data, **data}
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE memory SET data = ?, updated_at = ? "
                "WHERE entity_type = ? AND id = ?",
                (json.dumps(merged, default=str), now, entity_type, id),
            )
            conn.commit()
        return True

    async def delete(self, entity_type: str, id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM memory WHERE entity_type = ? AND id = ?",
                (entity_type, id),
            )
            conn.commit()
            return cur.rowcount > 0
