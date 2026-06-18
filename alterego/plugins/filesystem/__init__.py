"""Filesystem plugin — filesystem capability."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class FilesystemPlugin(BasePlugin):
    spec = BridgeSpec(
        name="filesystem",
        version="0.1.0",
        capabilities=["filesystem"],
        description="File operations: read, write, list, glob, copy, delete",
    )
    plugin_spec = PluginSpec(
        name="filesystem",
        version="0.1.0",
        capabilities=["filesystem"],
        priority=10,
        description="Filesystem: read, write, list, glob",
    )

    def methods(self) -> list[str]:
        return ["read", "write", "append", "list", "glob", "exists", "mkdir", "copy", "move", "delete", "info"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if method == "read":
            return self._read(**params)
        if method == "write":
            return self._write(**params)
        if method == "append":
            return self._append(**params)
        if method == "list":
            return self._list(**params)
        if method == "glob":
            return self._glob(**params)
        if method == "exists":
            return self._exists(**params)
        if method == "mkdir":
            return self._mkdir(**params)
        if method == "copy":
            return self._copy(**params)
        if method == "move":
            return self._move(**params)
        if method == "delete":
            return self._delete(**params)
        if method == "info":
            return self._info(**params)
        raise ValueError(f"unknown method: {method}")

    def _read(self, path: str, encoding: str = "utf-8") -> str:
        return Path(path).read_text(encoding=encoding)

    def _write(self, path: str, content: str, encoding: str = "utf-8") -> int:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return len(content)

    def _append(self, path: str, content: str) -> int:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(content)
        return len(content)

    def _list(self, path: str) -> list[dict[str, Any]]:
        p = Path(path)
        return [
            {"name": entry.name, "is_dir": entry.is_dir(), "size": entry.stat().st_size if entry.is_file() else 0}
            for entry in p.iterdir()
        ]

    def _glob(self, pattern: str, path: str = ".") -> list[str]:
        return [str(p) for p in Path(path).glob(pattern)]

    def _exists(self, path: str) -> bool:
        return Path(path).exists()

    def _mkdir(self, path: str, parents: bool = True) -> bool:
        Path(path).mkdir(parents=parents, exist_ok=True)
        return True

    def _copy(self, src: str, dest: str) -> bool:
        shutil.copy2(src, dest)
        return True

    def _move(self, src: str, dest: str) -> bool:
        shutil.move(src, dest)
        return True

    def _delete(self, path: str) -> bool:
        p = Path(path)
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
        return True

    def _info(self, path: str) -> dict[str, Any]:
        p = Path(path)
        if not p.exists():
            return {"exists": False}
        stat = p.stat()
        return {
            "exists": True,
            "path": str(p.resolve()),
            "name": p.name,
            "is_dir": p.is_dir(),
            "size": stat.st_size,
            "modified": stat.st_mtime,
        }

    async def initialize(self) -> None:
        pass

    async def health(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass
