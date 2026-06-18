"""Tests for the filesystem plugin (most self-contained)."""
import tempfile
from pathlib import Path

import pytest

from alterego.plugins.filesystem import FilesystemPlugin


@pytest.fixture
async def plugin():
    p = FilesystemPlugin()
    await p.initialize()
    return p


@pytest.mark.asyncio
async def test_write_and_read(plugin):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        path = f.name
    try:
        n = await plugin.call("write", {"path": path, "content": "hello world"})
        assert n == 11
        content = await plugin.call("read", {"path": path})
        assert content == "hello world"
    finally:
        Path(path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_exists(plugin):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "subdir" / "file.txt"
        await plugin.call("write", {"path": str(path), "content": "data"})
        assert await plugin.call("exists", {"path": str(path)})
        assert not await plugin.call("exists", {"path": str(path) + ".nope"})


@pytest.mark.asyncio
async def test_list(plugin):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.txt").write_text("a")
        (Path(tmp) / "b.txt").write_text("b")
        entries = await plugin.call("list", {"path": tmp})
        names = {e["name"] for e in entries}
        assert names == {"a.txt", "b.txt"}


@pytest.mark.asyncio
async def test_glob(plugin):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "x.py").write_text("")
        (Path(tmp) / "y.txt").write_text("")
        results = await plugin.call("glob", {"pattern": "*.py", "path": tmp})
        assert len(results) == 1
        assert results[0].endswith("x.py")


@pytest.mark.asyncio
async def test_info(plugin):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "info.txt"
        path.write_text("content")
        info = await plugin.call("info", {"path": str(path)})
        assert info["exists"]
        assert info["name"] == "info.txt"
        assert info["size"] == 7


@pytest.mark.asyncio
async def test_health(plugin):
    assert await plugin.health()


@pytest.mark.asyncio
async def test_unknown_method(plugin):
    with pytest.raises(ValueError, match="unknown method"):
        await plugin.call("nonexistent", {})
