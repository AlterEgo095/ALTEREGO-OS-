"""Filesystem plugin — filesystem capability.

V1.1: adds path traversal protection via configurable root.
Set ALTEREGO_FS_ROOT env var to enforce a sandbox.
If unset, plugin runs in unrestricted mode (with warning).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class FilesystemPlugin(BasePlugin):
    spec = BridgeSpec(
        name="filesystem",
        version="0.1.1",
        capabilities=["filesystem"],
        description="File operations: read, write, list, glob, copy, move, delete (with optional sandbox)",
    )
    plugin_spec = PluginSpec(
        name="filesystem",
        version="0.1.1",
        capabilities=["filesystem"],
        priority=10,
        description="Filesystem: read, write, list, glob (sandbox-aware)",
    )

    def __init__(self) -> None:
        self._root: Path | None = None  # None = unrestricted (with warning)

    async def initialize(self) -> None:
        root_env = os.environ.get("ALTEREGO_FS_ROOT")
        if root_env:
            self._root = Path(root_env).resolve()
            self._root.mkdir(parents=True, exist_ok=True)
            logger.info(f"filesystem plugin: sandboxed to {self._root}")
        else:
            logger.warning(
                "filesystem plugin: ALTEREGO_FS_ROOT not set — running UNRESTRICTED. "
                "Set this env var in production to enforce a sandbox."
            )

    def _resolve(self, path: str) -> Path:
        """Resolve a path and verify it's within the sandbox root (if configured)."""
        p = Path(path)
        if self._root is not None:
            if p.is_absolute():
                resolved = p.resolve()
            else:
                resolved = (self._root / p).resolve()
            try:
                resolved.relative_to(self._root)
            except ValueError:
                raise PermissionError(
                    f"path traversal blocked: '{path}' resolves to {resolved} which is outside sandbox root {self._root}"
                )
            return resolved
        return p.resolve()

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
        return self._resolve(path).read_text(encoding=encoding)

    def _write(self, path: str, content: str, encoding: str = "utf-8") -> int:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return len(content)

    def _append(self, path: str, content: str) -> int:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(content)
        return len(content)

    def _list(self, path: str) -> list[dict[str, Any]]:
        p = self._resolve(path)
        return [
            {"name": entry.name, "is_dir": entry.is_dir(), "size": entry.stat().st_size if entry.is_file() else 0}
            for entry in p.iterdir()
        ]

    def _glob(self, pattern: str, path: str = ".") -> list[str]:
        base = self._resolve(path)
        return [str(p) for p in base.glob(pattern)]

    def _exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def _mkdir(self, path: str, parents: bool = True) -> bool:
        self._resolve(path).mkdir(parents=parents, exist_ok=True)
        return True

    def _copy(self, src: str, dest: str) -> bool:
        src_p = self._resolve(src)
        dest_p = self._resolve(dest)
        shutil.copy2(src_p, dest_p)
        return True

    def _move(self, src: str, dest: str) -> bool:
        src_p = self._resolve(src)
        dest_p = self._resolve(dest)
        shutil.move(src_p, dest_p)
        return True

    def _delete(self, path: str) -> bool:
        p = self._resolve(path)
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
        return True

    def _info(self, path: str) -> dict[str, Any]:
        p = self._resolve(path)
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

    async def health(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass
