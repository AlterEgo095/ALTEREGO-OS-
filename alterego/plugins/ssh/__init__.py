"""SSH plugin — ssh capability."""
from __future__ import annotations

import os
from typing import Any

from loguru import logger
from paramiko import SSHClient, AutoAddPolicy

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class SSHPlugin(BasePlugin):
    spec = BridgeSpec(
        name="ssh",
        version="0.1.0",
        capabilities=["ssh"],
        description="SSH exec, scp via paramiko",
    )
    plugin_spec = PluginSpec(
        name="ssh",
        version="0.1.0",
        capabilities=["ssh"],
        priority=10,
        description="SSH: exec, scp, health",
    )

    def __init__(self) -> None:
        # V1: stateless per-call (open/close each time). V2: connection pool.
        pass

    async def initialize(self) -> None:
        ssh_dir = os.path.expanduser("~/.ssh")
        if not os.path.isdir(ssh_dir):
            logger.warning(f"no ~/.ssh directory — ssh plugin may fail to authenticate")

    def methods(self) -> list[str]:
        return ["exec", "scp_put", "scp_get", "health_check"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if method == "exec":
            return await self._exec(**params)
        if method == "scp_put":
            return await self._scp_put(**params)
        if method == "scp_get":
            return await self._scp_get(**params)
        if method == "health_check":
            return await self._health_check(**params)
        raise ValueError(f"unknown method: {method}")

    def _connect(self, host: str, user: str, port: int = 22, key_path: str | None = None) -> SSHClient:
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        key_path = key_path or os.path.expanduser("~/.ssh/id_rsa")
        client.connect(host, port=port, username=user, key_filename=key_path if os.path.exists(key_path) else None)
        return client

    async def _exec(self, host: str, user: str, command: str, port: int = 22, key_path: str | None = None) -> dict[str, Any]:
        client = self._connect(host, user, port, key_path)
        try:
            stdin, stdout, stderr = client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            return {
                "exit_code": exit_code,
                "stdout": stdout.read().decode("utf-8", errors="replace"),
                "stderr": stderr.read().decode("utf-8", errors="replace"),
            }
        finally:
            client.close()

    async def _scp_put(self, host: str, user: str, local: str, remote: str, port: int = 22, key_path: str | None = None) -> bool:
        from paramiko import Transport
        from paramiko.sftp_client import SFTPClient
        transport = Transport((host, port))
        key_path = key_path or os.path.expanduser("~/.ssh/id_rsa")
        from paramiko import RSAKey
        pkey = RSAKey.from_private_key_file(key_path) if os.path.exists(key_path) else None
        transport.connect(username=user, pkey=pkey)
        try:
            sftp = SFTPClient.from_transport(transport)
            sftp.put(local, remote)
            return True
        finally:
            transport.close()

    async def _scp_get(self, host: str, user: str, remote: str, local: str, port: int = 22, key_path: str | None = None) -> bool:
        from paramiko import Transport, RSAKey
        from paramiko.sftp_client import SFTPClient
        transport = Transport((host, port))
        key_path = key_path or os.path.expanduser("~/.ssh/id_rsa")
        pkey = RSAKey.from_private_key_file(key_path) if os.path.exists(key_path) else None
        transport.connect(username=user, pkey=pkey)
        try:
            sftp = SFTPClient.from_transport(transport)
            sftp.get(remote, local)
            return True
        finally:
            transport.close()

    async def _health_check(self, host: str, user: str, port: int = 22, key_path: str | None = None) -> dict[str, Any]:
        try:
            client = self._connect(host, user, port, key_path)
            client.close()
            return {"healthy": True, "host": host}
        except Exception as e:
            return {"healthy": False, "host": host, "error": str(e)}

    async def health(self) -> bool:
        return True  # always available; per-host health via _health_check

    async def shutdown(self) -> None:
        pass
