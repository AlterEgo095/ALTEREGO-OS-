"""Docker plugin — docker capability."""
from __future__ import annotations

from typing import Any

import docker
from loguru import logger

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class DockerPlugin(BasePlugin):
    spec = BridgeSpec(
        name="docker",
        version="0.1.0",
        capabilities=["docker"],
        description="Docker operations via docker-py",
    )
    plugin_spec = PluginSpec(
        name="docker",
        version="0.1.0",
        capabilities=["docker"],
        priority=10,
        description="Docker: ps, logs, restart, build, exec",
    )

    def __init__(self) -> None:
        self.client: docker.DockerClient | None = None

    async def initialize(self) -> None:
        try:
            self.client = docker.from_env()
            self.client.ping()
            logger.info("docker plugin: connected to Docker daemon")
        except Exception as e:
            logger.error(f"docker plugin: cannot connect to Docker: {e}")
            self.client = None

    def methods(self) -> list[str]:
        return ["ps", "logs", "restart", "stop", "start", "build", "exec", "stats"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if not self.client:
            raise RuntimeError("docker plugin not connected")
        if method == "ps":
            return await self._ps(**params)
        if method == "logs":
            return await self._logs(**params)
        if method == "restart":
            return await self._restart(**params)
        if method == "stop":
            return await self._stop(**params)
        if method == "start":
            return await self._start(**params)
        if method == "build":
            return await self._build(**params)
        if method == "exec":
            return await self._exec(**params)
        if method == "stats":
            return await self._stats(**params)
        raise ValueError(f"unknown method: {method}")

    async def _ps(self, all: bool = False) -> list[dict[str, Any]]:
        containers = self.client.containers.list(all=all)
        return [
            {
                "id": c.short_id,
                "name": c.name,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                "status": c.status,
            }
            for c in containers
        ]

    async def _logs(self, container: str, tail: int = 100) -> str:
        c = self.client.containers.get(container)
        return c.logs(tail=tail).decode("utf-8", errors="replace")

    async def _restart(self, container: str) -> bool:
        c = self.client.containers.get(container)
        c.restart()
        return True

    async def _stop(self, container: str) -> bool:
        c = self.client.containers.get(container)
        c.stop()
        return True

    async def _start(self, container: str) -> bool:
        c = self.client.containers.get(container)
        c.start()
        return True

    async def _build(self, path: str, tag: str) -> dict[str, Any]:
        image, _ = self.client.images.build(path=path, tag=tag)
        return {"image": image.id, "tags": image.tags}

    async def _exec(self, container: str, cmd: str) -> dict[str, Any]:
        c = self.client.containers.get(container)
        result = c.exec_run(cmd)
        return {
            "exit_code": result.exit_code,
            "output": result.output.decode("utf-8", errors="replace"),
        }

    async def _stats(self, container: str) -> dict[str, Any]:
        c = self.client.containers.get(container)
        s = c.stats(stream=False)
        cpu_delta = s["cpu_stats"]["cpu_usage"]["total_usage"] - s["precpu_stats"]["cpu_usage"]["total_usage"]
        sys_delta = s["cpu_stats"]["system_cpu_usage"] - s["precpu_stats"]["system_cpu_usage"]
        mem = s["memory_stats"].get("usage", 0)
        return {
            "container": c.name,
            "cpu_percent": (cpu_delta / sys_delta * 100) if sys_delta > 0 else 0,
            "memory_mb": mem / 1024 / 1024,
        }

    async def health(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    async def shutdown(self) -> None:
        pass
