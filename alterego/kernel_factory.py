"""ALTEREGO OS — Kernel factory.

Wires up the full V1.1 kernel with all engines and departments.
Single entry point for CLI and programmatic use.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from alterego.kernel import (
    CapabilityRegistry, CapabilitySpec, ChiefOfStaff, ConfidenceEngine,
    DecisionEngine, DepartmentLoader, InProcessEventBus, LearningEngine,
    Memory, MissionEngine, Planner, PluginManager, PolicyEngine, SQLiteMemory,
)


def build_kernel(
    db_path: str | Path = "./data/alterego.db",
    departments_dir: str | Path | None = None,
    policies_yaml: str | Path | None = None,
    auto_approve: bool = True,
) -> dict:
    """Build and wire the full V1.1 kernel.

    Returns a dict with all components for programmatic access.
    Note: plugins are discovered but NOT initialized (async). Call
    `await kernel['plugin_manager'].initialize_all()` separately if needed.
    """
    # 1. Infra
    memory = SQLiteMemory(db_path)
    bus = InProcessEventBus()

    # 2. Plugins (discovery is sync, initialization is async)
    pm = PluginManager()
    pm.discover()

    # If no plugins discovered via entry points (not pip-installed),
    # manually register the core plugins
    if not pm.list_plugins():
        from alterego.plugins.filesystem import FilesystemPlugin
        from alterego.plugins.llm import LLMPlugin
        fs = FilesystemPlugin()
        llm = LLMPlugin()
        pm._plugins["filesystem"] = fs
        pm._plugins["llm"] = llm
        pm._by_capability["filesystem"] = ["filesystem"]
        pm._by_capability["llm.chat"] = ["llm"]

    # 3. Capabilities
    cap_reg = CapabilityRegistry()
    _CAPABILITY_DESCRIPTIONS = {
        "github": "GitHub operations: clone, list_repos, get_repo_info, create_issue, create_pull_request, list_commits",
        "docker": "Docker: ps, logs, restart, stop, start, build, exec, stats",
        "ssh": "SSH: exec, scp_put, scp_get, health_check",
        "browser": "Browser: open, click, fill, screenshot, scrape, evaluate",
        "filesystem": "Filesystem: read, write, list, glob, copy, move, delete",
        "database.sql": "PostgreSQL: query, execute",
        "database.nosql": "MongoDB: find, insert, update, delete, count",
        "llm.chat": "LLM chat completion (OpenAI/Ollama)",
        "email": "Send email via SMTP",
        "telegram": "Send Telegram notifications",
    }
    for cap_name in pm.list_capabilities():
        cap_reg.register(CapabilitySpec(
            name=cap_name,
            description=_CAPABILITY_DESCRIPTIONS.get(cap_name, ""),
        ))

    # 4. V1.1 Engines
    policy = PolicyEngine(policies_yaml=Path(policies_yaml) if policies_yaml else None)

    # LLM plugin for Planner/Decision
    llm_plugin = pm.best_for("llm.chat")

    # 5. V1.2 Validation Pipeline (before MissionEngine which uses it)
    from alterego.kernel.validation_pipeline import ValidationPipeline
    validation = ValidationPipeline(llm_plugin=llm_plugin)

    # 6. Core engines
    planner = Planner(capability_registry=cap_reg, llm_plugin=llm_plugin) if llm_plugin else None
    decision = DecisionEngine(memory=memory, planner=planner, llm_plugin=llm_plugin) if llm_plugin else None
    mission_engine = MissionEngine(memory=memory, event_bus=bus, decision_engine=decision, plugin_manager=pm, validation_pipeline=validation)

    # 7. V1.1 Engines
    confidence = ConfidenceEngine(plugin_manager=pm, policy_engine=policy, memory=memory)
    learning = LearningEngine(memory=memory, event_bus=bus)

    # 7.1 V1.3 — Initiative Engine + Digital Twin
    from alterego.kernel.initiative_engine import InitiativeEngine
    from alterego.kernel.digital_twin import DigitalTwin
    initiative = InitiativeEngine(memory=memory, event_bus=bus, chief_of_staff=None, auto_create_missions=False)
    digital_twin = DigitalTwin(memory=memory)

    # 7.2 V2 — Goal Engine + Daily Assistant + Context Engine
    from alterego.kernel.goal_engine import GoalEngine
    from alterego.kernel.daily_assistant import DailyAssistant
    from alterego.kernel.context_engine import ContextEngine
    goal_engine = GoalEngine(memory=memory, llm_plugin=llm_plugin)
    daily = DailyAssistant(memory=memory, goal_engine=goal_engine, initiative_engine=initiative, llm_plugin=llm_plugin)
    context = ContextEngine(memory=memory, digital_twin=digital_twin, goal_engine=goal_engine)

    # 7.3 V2.1 — Real Life Connection
    from alterego.kernel.digital_twin_v2 import DigitalTwinV2
    from alterego.kernel.life_timeline import LifeTimeline
    from alterego.kernel.long_term_memory import LongTermMemory
    from alterego.kernel.unified_workspace import UnifiedWorkspace
    twin_v2 = DigitalTwinV2(memory=memory)
    timeline = LifeTimeline(memory=memory, event_bus=bus)
    long_term = LongTermMemory(memory=memory, timeline=timeline)
    workspace = UnifiedWorkspace(plugin_manager=pm, digital_twin=twin_v2)

    # 7. Departments
    if departments_dir is None:
        # Default to the repo's departments/ directory
        repo_root = Path(__file__).resolve().parent.parent
        departments_dir = repo_root / "departments"
    dept_loader = DepartmentLoader(Path(departments_dir))
    dept_loader.load_all()

    # 8. Chief Of Staff (V1.1)
    cos = ChiefOfStaff(
        mission_engine=mission_engine,
        memory=memory,
        event_bus=bus,
        policy_engine=policy,
        confidence_engine=confidence,
        learning_engine=learning,
        auto_approve=auto_approve,
    )

    return {
        "chief_of_staff": cos,
        "mission_engine": mission_engine,
        "memory": memory,
        "event_bus": bus,
        "plugin_manager": pm,
        "capability_registry": cap_reg,
        "policy_engine": policy,
        "confidence_engine": confidence,
        "learning_engine": learning,
        "department_loader": dept_loader,
        "llm_plugin": llm_plugin,
        "validation_pipeline": validation,
        "initiative_engine": initiative,
        "digital_twin": digital_twin,
        "goal_engine": goal_engine,
        "daily_assistant": daily,
        "context_engine": context,
        # V2.1
        "digital_twin_v2": twin_v2,
        "life_timeline": timeline,
        "long_term_memory": long_term,
        "unified_workspace": workspace,
    }
