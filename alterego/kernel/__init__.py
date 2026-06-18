"""ALTEREGO OS Kernel — V1.

8 components:
  - ChiefOfStaff      (entry point, conversational)
  - MissionEngine     (mission lifecycle)
  - DecisionEngine    (analysis + routing)
  - Planner           (DAG decomposition)
  - Memory            (centralized, 10 entities)
  - EventBus          (in-process pub/sub, V1)
  - CapabilityRegistry(selects capability, not plugin)
  - PluginManager     (loads plugins, picks best for capability)
"""

from alterego.kernel.base import (
    BaseBridge,
    BasePlugin,
    BaseCapability,
    BridgeSpec,
    PluginSpec,
    CapabilitySpec,
    Mission,
    MissionStatus,
    Event,
)
from alterego.kernel.event_bus import EventBus, InProcessEventBus
from alterego.kernel.memory import Memory, SQLiteMemory
from alterego.kernel.capability_registry import CapabilityRegistry
from alterego.kernel.plugin_manager import PluginManager
from alterego.kernel.planner import Planner
from alterego.kernel.decision_engine import DecisionEngine
from alterego.kernel.mission_engine import MissionEngine
from alterego.kernel.chief_of_staff import ChiefOfStaff

__all__ = [
    # Base contracts
    "BaseBridge", "BasePlugin", "BaseCapability",
    "BridgeSpec", "PluginSpec", "CapabilitySpec",
    "Mission", "MissionStatus", "Event",
    # Concrete implementations
    "EventBus", "InProcessEventBus",
    "Memory", "SQLiteMemory",
    "CapabilityRegistry", "PluginManager",
    "Planner", "DecisionEngine", "MissionEngine", "ChiefOfStaff",
]
