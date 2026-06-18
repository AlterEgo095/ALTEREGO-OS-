"""ALTEREGO OS Kernel — V1.1.

11 components (V1.1 adds 3 engines + departments):
  - ChiefOfStaff      (entry point, conversational)
  - MissionEngine     (mission lifecycle)
  - DecisionEngine    (analysis + routing)
  - Planner           (DAG decomposition)
  - Memory            (centralized, 10 entities)
  - EventBus          (in-process pub/sub, V1)
  - CapabilityRegistry(selects capability, not plugin)
  - PluginManager     (loads plugins, picks best for capability)
  - PolicyEngine      (NEW V1.1: decides allow/deny/require_approval)
  - ConfidenceEngine  (NEW V1.1: scores each mission 0-100)
  - LearningEngine    (NEW V1.1: captures feedback, improves over time)
  - DepartmentLoader  (NEW V1.1: departments as YAML config)
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
from alterego.kernel.policy_engine import PolicyEngine, PolicyDecision, RiskLevel
from alterego.kernel.confidence_engine import ConfidenceEngine
from alterego.kernel.learning_engine import LearningEngine
from alterego.kernel.departments import DepartmentLoader, DepartmentSpec

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
    # V1.1 — new engines
    "PolicyEngine", "PolicyDecision", "RiskLevel",
    "ConfidenceEngine", "LearningEngine",
    "DepartmentLoader", "DepartmentSpec",
]
