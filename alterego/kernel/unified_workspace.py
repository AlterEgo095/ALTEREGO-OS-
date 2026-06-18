"""ALTEREGO OS V2.1 — Unified Workspace.

ALTEREGO voit tout l'environnement numérique depuis une interface unique :
  GitHub, Docker, VPS, SSH, Documents, PDF, Emails, Telegram,
  WhatsApp, Calendrier, Cloud, Notes, Bases de données, APIs externes.

L'utilisateur ne navigue plus entre plusieurs outils.
ALTEREGO devient l'interface unique.

Le Unified Workspace est une couche d'abstraction au-dessus des plugins
qui fournit une vue consolidée de tous les outils connectés.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger


class UnifiedWorkspace:
    """Single pane of glass for all connected tools.

    Provides:
    - overview() — what's connected, what's healthy, what's available
    - list_resources() — all resources across all tools
    - search() — search across all tools
    - status() — health of each connection
    """

    def __init__(self, plugin_manager: Any, digital_twin: Any = None) -> None:
        self.pm = plugin_manager
        self.twin = digital_twin

    async def overview(self) -> dict[str, Any]:
        """Get a consolidated overview of all connected tools."""
        overview = {
            "generated_at": datetime.utcnow().isoformat(),
            "connections": {},
            "total_plugins": len(self.pm.list_plugins()),
            "total_capabilities": len(self.pm.list_capabilities()),
        }

        for plugin_name in self.pm.list_plugins():
            plugin = self.pm.get(plugin_name)
            try:
                healthy = await plugin.health()
            except Exception:
                healthy = False

            overview["connections"][plugin_name] = {
                "healthy": healthy,
                "capabilities": plugin.plugin_spec.capabilities,
                "methods": plugin.methods(),
            }

        # Count healthy vs unhealthy
        healthy_count = sum(1 for c in overview["connections"].values() if c["healthy"])
        overview["healthy_connections"] = healthy_count
        overview["unhealthy_connections"] = len(overview["connections"]) - healthy_count

        return overview

    async def status(self) -> list[dict[str, Any]]:
        """Get health status of all connections."""
        statuses = []
        for name in self.pm.list_plugins():
            plugin = self.pm.get(name)
            try:
                healthy = await plugin.health()
            except Exception:
                healthy = False
            statuses.append({
                "name": name,
                "healthy": healthy,
                "capabilities": plugin.plugin_spec.capabilities,
            })
        return statuses

    async def list_resources(self) -> dict[str, list[dict[str, Any]]]:
        """List all resources across all connected tools.

        This is a best-effort scan — not all plugins support listing.
        """
        resources = {}

        # GitHub repos
        github = self.pm.best_for("github")
        if github and await github.health():
            try:
                repos = await github.call("list_repos", {"limit": 10})
                resources["github_repos"] = repos
            except Exception:
                pass

        # Docker containers
        docker = self.pm.best_for("docker")
        if docker:
            try:
                healthy = await docker.health()
                if healthy:
                    containers = await docker.call("ps", {"all": True})
                    resources["docker_containers"] = containers
            except Exception:
                pass

        # Filesystem (sandbox root)
        fs = self.pm.best_for("filesystem")
        if fs:
            try:
                # List root of sandbox
                import os
                root = os.environ.get("ALTEREGO_FS_ROOT", ".")
                entries = await fs.call("list", {"path": root})
                resources["filesystem"] = entries[:20]  # limit
            except Exception:
                pass

        # Digital Twin entities
        if self.twin:
            try:
                profile = await self.twin.get_full_profile() if hasattr(self.twin, "get_full_profile") else {}
                for key, val in profile.items():
                    if isinstance(val, list) and val:
                        resources[f"twin_{key}"] = val[:10]
            except Exception:
                pass

        return resources

    async def search(self, query: str) -> dict[str, Any]:
        """Search across all available tools.

        V1: searches filesystem (glob) and Digital Twin.
        V2 will add GitHub, emails, documents, etc.
        """
        results = {"query": query, "found": {}}

        # Filesystem search
        fs = self.pm.best_for("filesystem")
        if fs:
            try:
                import os
                root = os.environ.get("ALTEREGO_FS_ROOT", ".")
                files = await fs.call("glob", {"pattern": f"*{query}*", "path": root})
                if files:
                    results["found"]["filesystem"] = files[:10]
            except Exception:
                pass

        # Memory search (conversations, tasks)
        # This requires direct memory access — skip for V1 if not available

        results["total_results"] = sum(len(v) for v in results["found"].values())
        return results

    async def describe(self) -> str:
        """Human-readable workspace overview."""
        overview = await self.overview()
        lines = [
            "🌐 Unified Workspace",
            f"  Plugins: {overview['total_plugins']} ({overview['healthy_connections']} healthy, {overview['unhealthy_connections']} unhealthy)",
            f"  Capabilities: {overview['total_capabilities']}",
            "",
            "── Connections ──",
        ]

        for name, info in overview["connections"].items():
            icon = "✅" if info["healthy"] else "❌"
            caps = ", ".join(info["capabilities"])
            lines.append(f"  {icon} {name} ({caps})")

        # Resources
        resources = await self.list_resources()
        if resources:
            lines.append("")
            lines.append("── Resources ──")
            for category, items in resources.items():
                lines.append(f"  {category}: {len(items)} item(s)")

        return "\n".join(lines)
