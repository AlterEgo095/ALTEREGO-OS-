"""Tests for the centralized Memory (SQLite)."""
import tempfile
from pathlib import Path

import pytest

from alterego.kernel.memory import SQLiteMemory, ENTITY_TYPES


@pytest.fixture
async def memory():
    with tempfile.TemporaryDirectory() as tmp:
        m = SQLiteMemory(Path(tmp) / "test.db")
        yield m


@pytest.mark.asyncio
async def test_put_and_get(memory):
    record_id = await memory.put("projects", {"name": "alterego", "stars": 100})
    rec = await memory.get("projects", record_id)
    assert rec is not None
    assert rec.data["name"] == "alterego"
    assert rec.data["stars"] == 100


@pytest.mark.asyncio
async def test_get_nonexistent(memory):
    rec = await memory.get("projects", "does-not-exist")
    assert rec is None


@pytest.mark.asyncio
async def test_query_with_filter(memory):
    await memory.put("repositories", {"name": "langchain", "language": "python"})
    await memory.put("repositories", {"name": "next.js", "language": "typescript"})
    await memory.put("repositories", {"name": "crewai", "language": "python"})

    py_repos = await memory.query("repositories", language="python")
    assert len(py_repos) == 2
    assert all(r.data["language"] == "python" for r in py_repos)


@pytest.mark.asyncio
async def test_update(memory):
    rid = await memory.put("tasks", {"status": "created", "objective": "test"})
    ok = await memory.update("tasks", rid, {"status": "completed"})
    assert ok
    rec = await memory.get("tasks", rid)
    assert rec.data["status"] == "completed"
    assert rec.data["objective"] == "test"  # preserved


@pytest.mark.asyncio
async def test_delete(memory):
    rid = await memory.put("tasks", {"status": "created"})
    ok = await memory.delete("tasks", rid)
    assert ok
    rec = await memory.get("tasks", rid)
    assert rec is None


@pytest.mark.asyncio
async def test_invalid_entity_type(memory):
    with pytest.raises(ValueError):
        await memory.put("invalid_type", {"foo": "bar"})


def test_all_entity_types_present():
    expected = {
        "projects", "repositories", "servers", "containers",
        "users", "conversations", "tasks", "documents",
        "preferences", "knowledge",
    }
    assert set(ENTITY_TYPES) == expected
    assert len(ENTITY_TYPES) == 10
