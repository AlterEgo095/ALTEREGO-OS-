"""ALTEREGO OS — Capability Registry.

The Kernel NEVER selects a plugin. It selects a CAPABILITY.
The Plugin Manager picks the best plugin for that capability.

This indirection is critical: it lets us swap PyGithub → github3.py without
touching the Decision Engine or Planner.
"""
from __future__ import annotations

from loguru import logger

from alterego.kernel.base import CapabilitySpec


class CapabilityRegistry:
    """Holds the catalog of capabilities the system can provide.

    A capability is an abstract intent like `github`, `llm.chat`, `database.sql`.
    Each capability is mapped to one or more plugins that can fulfill it.
    """

    def __init__(self) -> None:
        self._caps: dict[str, CapabilitySpec] = {}

    def register(self, spec: CapabilitySpec) -> None:
        if spec.name in self._caps:
            logger.warning(f"capability '{spec.name}' already registered — overwriting")
        self._caps[spec.name] = spec
        logger.debug(f"capability registered: {spec.name}")

    def get(self, name: str) -> CapabilitySpec | None:
        return self._caps.get(name)

    def list(self) -> list[CapabilitySpec]:
        return list(self._caps.values())

    def exists(self, name: str) -> bool:
        return name in self._caps

    def describe(self) -> str:
        """Human-readable summary for the Decision Engine (LLM)."""
        lines = []
        for cap in self._caps.values():
            req = ", ".join(cap.required_plugins) if cap.required_plugins else "—"
            lines.append(f"  - {cap.name}: {cap.description} (plugins: {req})")
        return "\n".join(lines)
