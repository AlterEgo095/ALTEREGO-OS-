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

    Returns a dict with all components for programmatic access:
        {
            "chief_of_staff": ChiefOfStaff,
            "mission_engine": MissionEngine,
            "memory": Memory,
            "event_bus": EventBus,
            "plugin_manager": PluginManager,
            "capability_registry": CapabilityRegistry,
            "policy_engine": PolicyEngine,
            "confidence_engine": ConfidenceEngine,
            "learning_engine": LearningEngine,
            "department_loader": DepartmentLoader,
        }
    """
    import asyncio

    # 1. Infra
    memory = SQLiteMemory(db_path)
    bus = InProcessEventBus()

    # 2. Plugins
    pm = PluginManager()
    pm.discover()
    asyncio.run(pm.initialize_all())

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

    # 5. Core engines
    planner = Planner(capability_registry=cap_reg, llm_plugin=llm_plugin) if llm_plugin else None
    decision = DecisionEngine(memory=memory, planner=planner, llm_plugin=llm_plugin) if llm_plugin else None
    mission_engine = MissionEngine(memory=memory, event_bus=bus, decision_engine=decision, plugin_manager=pm)

    # 6. V1.1 Engines
    confidence = ConfidenceEngine(plugin_manager=pm, policy_engine=policy, memory=memory)
    learning = LearningEngine(memory=memory, event_bus=bus)

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
    }
