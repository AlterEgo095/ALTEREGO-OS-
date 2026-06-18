"""PHASE 3A.4 — Daily Operations : Multi-department Orchestration.

Scenario:
  User: "Vérifie mon VPS, résume les nouveautés IA de la semaine, et prépare-moi un rapport"

  This mission touches 3 departments:
  - Infrastructure (VPS check via SSH/filesystem)
  - Research (web research for AI news)
  - Personal (compile report, save to documents)

  ALTEREGO should:
  1. Plan touches multiple capabilities across departments
  2. Confidence: medium (multiple capabilities, some HIGH risk)
  3. Policy: filesystem.read ALLOW, ssh.exec REQUIRE_APPROVAL, browser ALLOW
  4. Execute with policy awareness
  5. Learning captures cross-department outcome
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec
from alterego.kernel import (
    CapabilityRegistry, CapabilitySpec, ChiefOfStaff, ConfidenceEngine,
    DecisionEngine, DepartmentLoader, InProcessEventBus, LearningEngine,
    MissionEngine, Planner, PluginManager, PolicyEngine, SQLiteMemory,
)


class MultiDeptLLM(BasePlugin):
    """Mock LLM that produces a multi-department plan."""
    spec = BridgeSpec(name="multi_llm", capabilities=["llm.chat"])
    plugin_spec = PluginSpec(name="multi_llm", capabilities=["llm.chat"], priority=10)
    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["chat"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        system = params.get("system", "")
        user = params.get("user", "")

        if "extract the user's intent" in system:
            return {"content": "Multi-department mission: check VPS health, research AI news, compile a report."}

        if "Available capabilities" in system:
            plan = {"tasks": [
                # Infrastructure department
                {"step": 1, "description": "Check VPS CPU and RAM", "capability": "filesystem", "method": "read", "params": {"path": "/proc/loadavg"}},
                {"step": 2, "description": "Check VPS memory", "capability": "filesystem", "method": "read", "params": {"path": "/proc/meminfo"}},
                # Research department
                {"step": 3, "description": "Fetch AI news page", "capability": "browser", "method": "open", "params": {"url": "https://example.com/ai-news"}},
                {"step": 4, "description": "Extract AI news content", "capability": "browser", "method": "scrape", "params": {"selector": "body"}},
                # Personal department (compile report)
                {"step": 5, "description": "Compile the report", "capability": "llm.chat", "method": "chat", "params": {"system": "Compile a report from VPS stats and AI news.", "user": user}},
            ]}
            return {"content": json.dumps(plan)}

        return {"content": "Report compiled. VPS is healthy. AI news: GPT-5 released, LangChain 1.0 announced."}


class MockBrowserPlugin(BasePlugin):
    spec = BridgeSpec(name="mock_browser", capabilities=["browser"])
    plugin_spec = PluginSpec(name="mock_browser", capabilities=["browser"], priority=10)
    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["open", "scrape"]
    async def call(self, method, params):
        if method == "open":
            return {"url": params.get("url"), "title": "AI News", "status": 200}
        if method == "scrape":
            return {"text": "AI news this week: GPT-5 released, LangChain 1.0 announced, new RAG techniques.", "truncated": False}
        return {}


async def main():
    print("=" * 70)
    print("PHASE 3A.4 — DAILY OPS : MULTI-DEPARTMENT ORCHESTRATION")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmp:
        memory = SQLiteMemory(Path(tmp) / "test.db")
        bus = InProcessEventBus()
        pm = PluginManager()

        # Filesystem (real, for reading /proc)
        from alterego.plugins.filesystem import FilesystemPlugin
        import os
        os.environ.pop("ALTEREGO_FS_ROOT", None)
        fs = FilesystemPlugin()
        await fs.initialize()
        pm._plugins["filesystem"] = fs
        pm._by_capability["filesystem"] = ["filesystem"]

        # Browser (mock)
        browser = MockBrowserPlugin()
        await browser.initialize()
        pm._plugins["mock_browser"] = browser
        pm._by_capability["browser"] = ["mock_browser"]

        # LLM
        llm = MultiDeptLLM()
        await llm.initialize()
        pm._plugins["multi_llm"] = llm
        pm._by_capability["llm.chat"] = ["multi_llm"]

        # Capabilities
        cap_reg = CapabilityRegistry()
        cap_reg.register(CapabilitySpec(name="filesystem", description="File ops"))
        cap_reg.register(CapabilitySpec(name="browser", description="Browser"))
        cap_reg.register(CapabilitySpec(name="llm.chat", description="LLM"))
        cap_reg.register(CapabilitySpec(name="ssh", description="SSH"))  # declared but no plugin

        # Departments
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        dept_loader = DepartmentLoader(repo_root / "departments")
        depts = dept_loader.load_all()

        print(f"\n── Departments loaded: {len(depts)} ──")
        for d in depts:
            print(f"  - {d.name}: {', '.join(d.capabilities)}")

        # Engines
        policy = PolicyEngine()
        planner = Planner(cap_reg, llm)
        decision = DecisionEngine(memory, planner, llm)
        mission_engine = MissionEngine(memory, bus, decision, pm)
        confidence = ConfidenceEngine(pm, policy, memory)
        learning = LearningEngine(memory, bus)

        cos = ChiefOfStaff(
            mission_engine=mission_engine, memory=memory, event_bus=bus,
            policy_engine=policy, confidence_engine=confidence,
            learning_engine=learning, auto_approve=True,
        )

        # Multi-department mission
        print("\n── Mission : Vérifie mon VPS, résume les nouveautés IA, prépare un rapport ──\n")
        start = time.perf_counter()
        response = await cos.chat("Vérifie mon VPS, résume les nouveautés IA de la semaine, et prépare-moi un rapport")
        elapsed = time.perf_counter() - start

        print(response)
        print(f"\n  Temps: {elapsed*1000:.0f} ms")

        # Check which departments were involved
        tasks = await memory.query("tasks")
        knowledge = await memory.query("knowledge")

        # Determine departments involved
        capabilities_used = set()
        for t in tasks:
            for task in t.data.get("plan", []):
                capabilities_used.add(task.get("capability", ""))

        depts_involved = set()
        for cap in capabilities_used:
            for d in dept_loader.find_for_capability(cap):
                depts_involved.add(d.name)

        print(f"\n── Départements impliqués ──")
        for d in depts_involved:
            print(f"  ✓ {d}")

        print(f"\n── Capacités utilisées ──")
        for cap in capabilities_used:
            print(f"  ✓ {cap}")

        criteria = {
            "mission_completed": "Mission terminée" in response,
            "confidence_displayed": "Confiance" in response,
            "multiple_departments": len(depts_involved) >= 2,
            "multiple_capabilities": len(capabilities_used) >= 2,
            "learning_captured": len(knowledge) > 0,
            "no_architecture_leak": all(term not in response for term in ["BaseBridge", "PluginManager", "DepartmentLoader"]),
            "conversational": not response.startswith("{") and "Traceback" not in response,
        }

        print(f"\n── Critères de validation ──")
        for k, v in criteria.items():
            print(f"  {'✓' if v else '✗'} {k}")

        passed = all(criteria.values())
        print(f"\nPHASE 3A.4 (Multi-department): {'✓ PASS' if passed else '✗ FAIL'}")

        out = Path(__file__).resolve().parent.parent / "results" / "phase3a_04_multi_dept.json"
        out.write_text(json.dumps({
            "scenario": "3A.4 — Multi-department Orchestration",
            "passed": passed,
            "criteria": criteria,
            "departments_involved": list(depts_involved),
            "capabilities_used": list(capabilities_used),
            "elapsed_ms": round(elapsed * 1000, 1),
        }, indent=2))
        print(f"Results saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())
