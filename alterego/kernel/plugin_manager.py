"""ALTEREGO OS — Plugin Manager.

Discovers plugins via Python entry points, loads them, and picks the best
plugin for a given capability.

V1 strategy: load all plugins from `alterego.plugins` entry points group.
Pick best plugin for a capability by priority (lower number wins).
"""
from __future__ import annotations

from importlib.metadata import entry_points
from typing import Optional

from loguru import logger

from alterego.kernel.base import BasePlugin, BridgeSpec


class PluginManager:
    """Loads plugins and serves them by capability."""

    def __init__(self) -> None:
        # name -> plugin instance
        self._plugins: dict[str, BasePlugin] = {}
        # capability -> list of plugin names (sorted by priority)
        self._by_capability: dict[str, list[str]] = {}

    def discover(self) -> list[str]:
        """Discover plugins via entry points. Does NOT initialize them.

        Returns the list of discovered plugin names.
        """
        discovered = []
        try:
            eps = entry_points(group="alterego.plugins")
        except TypeError:
            # Python < 3.10 fallback
            eps = entry_points().get("alterego.plugins", [])
        for ep in eps:
            try:
                plugin_cls = ep.load()
                spec = plugin_cls.plugin_spec  # type: ignore[attr-defined]
                self._plugins[spec.name] = plugin_cls()  # instantiate
                for cap in spec.capabilities:
                    self._by_capability.setdefault(cap, []).append(spec.name)
                    # Sort by priority
                    self._by_capability[cap].sort(
                        key=lambda n: self._plugins[n].plugin_spec.priority
                    )
                discovered.append(spec.name)
                logger.info(f"plugin discovered: {spec.name} (caps: {spec.capabilities})")
            except Exception as e:
                logger.error(f"failed to load plugin '{ep.name}': {e}")
        return discovered

    async def initialize_all(self) -> None:
        """Initialize all discovered plugins (call their `initialize` hook)."""
        for name, plugin in self._plugins.items():
            try:
                await plugin.initialize()
                logger.debug(f"plugin initialized: {name}")
            except Exception as e:
                logger.error(f"plugin '{name}' failed to initialize: {e}")

    async def shutdown_all(self) -> None:
        for name, plugin in list(self._plugins.items()):
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.warning(f"plugin '{name}' shutdown error: {e}")

    def get(self, name: str) -> Optional[BasePlugin]:
        return self._plugins.get(name)

    def best_for(self, capability: str) -> Optional[BasePlugin]:
        """Return the best available plugin for a capability, or None."""
        candidates = self._by_capability.get(capability, [])
        for name in candidates:
            plugin = self._plugins[name]
            # V1: just return the first one (already sorted by priority).
            # V2: call plugin.health() and skip unhealthy ones.
            return plugin
        return None

    def list_plugins(self) -> list[str]:
        return list(self._plugins.keys())

    def list_capabilities(self) -> list[str]:
        return list(self._by_capability.keys())

    def describe(self) -> str:
        """Human-readable summary."""
        lines = ["Plugins loaded:"]
        for name, p in self._plugins.items():
            caps = ", ".join(p.plugin_spec.capabilities)
            lines.append(f"  - {name} (priority={p.plugin_spec.priority}, caps: {caps})")
        return "\n".join(lines)
