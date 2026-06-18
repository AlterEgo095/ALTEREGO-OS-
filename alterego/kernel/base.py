"""ALTEREGO OS — Base contracts.

Every plugin, bridge, and capability inherits from these ABCs.
The Kernel never knows concrete implementations — only contracts.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Specs (declarative metadata)
# ─────────────────────────────────────────────────────────────────────────────
class BridgeSpec(BaseModel):
    """Static metadata describing a bridge/plugin."""
    name: str
    version: str = "0.1.0"
    capabilities: list[str] = Field(default_factory=list)
    description: str = ""
    author: str = ""
    license: str = "MIT"


class PluginSpec(BaseModel):
    """Plugin metadata, including health/availability."""
    name: str
    version: str = "0.1.0"
    capabilities: list[str]
    priority: int = 50  # lower = higher priority when competing for same capability
    description: str = ""


class CapabilitySpec(BaseModel):
    """Describes one capability the system can provide."""
    name: str  # e.g. "github", "llm.chat", "database.sql"
    description: str = ""
    required_plugins: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Mission & Event
# ─────────────────────────────────────────────────────────────────────────────
class MissionStatus(str, Enum):
    CREATED = "created"
    PLANNED = "planned"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Mission(BaseModel):
    """A user-requested mission."""
    id: str
    objective: str  # natural language
    user_id: str = "default"
    status: MissionStatus = MissionStatus.CREATED
    plan: Optional[list[dict]] = None  # list of tasks (DAG flattened, V1)
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


class Event(BaseModel):
    """An event published on the bus."""
    subject: str  # e.g. "mission.created"
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = ""  # which component emitted


# ─────────────────────────────────────────────────────────────────────────────
# Base ABCs
# ─────────────────────────────────────────────────────────────────────────────
class BaseCapability(ABC):
    """Marker base for typed capabilities. V1 keeps it minimal."""

    @abstractmethod
    def spec(self) -> CapabilitySpec:
        ...


class BaseBridge(ABC):
    """All plugins inherit from this.

    The Kernel only knows `BaseBridge` — never the concrete DockerBridge, GitHubBridge, etc.
    A plugin IS a bridge in V1 (no separation yet; that comes when plugins grow).
    """

    spec: BridgeSpec

    @abstractmethod
    async def call(self, method: str, params: dict[str, Any]) -> Any:
        """Invoke a method by name with parameters."""
        ...

    @abstractmethod
    def methods(self) -> list[str]:
        """Return the list of exposed method names."""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Health check. Returns True if the bridge is operational."""
        ...

    def events_produced(self) -> list[str]:
        """Event subjects this bridge may publish. Override if needed."""
        return []


class BasePlugin(BaseBridge):
    """A plugin is a bridge with explicit PluginSpec and lifecycle hooks.

    V1 simplification: Plugin = Bridge. V2 may split (a plugin can host multiple bridges).
    """

    plugin_spec: PluginSpec

    async def initialize(self) -> None:
        """Called once when the plugin is loaded. Optional override."""
        pass

    async def shutdown(self) -> None:
        """Called when the plugin is unloaded. Optional override."""
        pass
