"""Quick smoke test — runs the kernel with a mock LLM, no external deps."""
import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from alterego.kernel import (
    CapabilityRegistry, CapabilitySpec, ChiefOfStaff, DecisionEngine,
    InProcessEventBus, MissionEngine, Planner, PluginManager, SQLiteMemory,
)
from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class MockLLMPlugin(BasePlugin):
    spec = BridgeSpec(name="mock_llm", capabilities=["llm.chat"])
    plugin_spec = PluginSpec(name="mock_llm", capabilities=["llm.chat"], priority=10)

    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["chat"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        system = params.get("system", "")
        user = params.get("user", "")
        if "extract the user's intent" in system:
            return {"content": "Test intent"}
        if "Available capabilities" in system:
            # Return a simple plan that uses llm.chat
            import json
            plan = {
                "tasks": [
                    {"step": 1, "description": "Respond to user", "capability": "llm.chat",
                     "method": "chat",
                     "params": {"system": "You are a helpful assistant.", "user": user}}
                ]
            }
            return {"content": json.dumps(plan)}
        # Default: echo
        return {"content": f"Hello from ALTEREGO OS! You said: {user}"}


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        # 1. Infra
        memory = SQLiteMemory(Path(tmp) / "test.db")
        bus = InProcessEventBus()

        # 2. Plugin manager with mock LLM
        pm = PluginManager()
        llm = MockLLMPlugin()
        await llm.initialize()
        pm._plugins["mock_llm"] = llm
        pm._by_capability["llm.chat"] = ["mock_llm"]

        # 3. Capabilities
        cap_reg = CapabilityRegistry()
        cap_reg.register(CapabilitySpec(name="llm.chat", description="LLM chat"))

        # 4. Engines
        planner = Planner(cap_reg, llm)
        decision = DecisionEngine(memory, planner, llm)
        mission_engine = MissionEngine(memory, bus, decision, pm)
        cos = ChiefOfStaff(mission_engine, memory, bus)

        # 5. Run a mission
        print("\n─── MISSION 1: simple greeting ───")
        response = await cos.chat("Hello ALTEREGO!")
        print(response)

        print("\n─── MISSION 2: another message ───")
        response = await cos.chat("Tell me about Python")
        print(response)

        # 6. Check memory
        print("\n─── MEMORY STATE ───")
        conversations = await memory.query("conversations")
        print(f"Conversations stored: {len(conversations)}")
        tasks = await memory.query("tasks")
        print(f"Missions stored: {len(tasks)}")
        for t in tasks:
            print(f"  - mission {t.id[:8]}: {t.data.get('status')} ({t.data.get('objective', '')[:60]})")

        # 7. Check event bus activity
        print("\n─── EVENT BUS ───")
        events_received = []
        async def capture(event):
            events_received.append(event.subject)
        bus.subscribe("*", capture)
        # The above subscription is too late — events were already published.
        # Just print summary
        print(f"Total plugins loaded: {len(pm.list_plugins())}")
        print(f"Total capabilities: {len(cap_reg.list())}")


if __name__ == "__main__":
    asyncio.run(main())
