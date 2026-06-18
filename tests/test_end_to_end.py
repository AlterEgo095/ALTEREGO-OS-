"""End-to-end test: full kernel pipeline with mock LLM + filesystem plugin."""
import tempfile
from pathlib import Path
from typing import Any

import pytest

from alterego.kernel import (
    CapabilityRegistry, CapabilitySpec, ChiefOfStaff, DecisionEngine,
    InProcessEventBus, MissionEngine, Planner, PluginManager, SQLiteMemory,
)
from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class EchoLLMPlugin(BasePlugin):
    """Mock LLM that returns a simple plan: write a file with the user's message."""
    spec = BridgeSpec(name="echo_llm", capabilities=["llm.chat"])
    plugin_spec = PluginSpec(
        name="echo_llm", version="0.1.0", capabilities=["llm.chat"], priority=10
    )

    def __init__(self):
        self.last_user_msg = ""

    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["chat"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if method == "chat":
            user = params.get("user", "")
            self.last_user_msg = user
            # If we're being asked to plan, return a plan
            if "Available capabilities" in params.get("system", ""):
                return {
                    "content": '{"tasks": [{"step": 1, "description": "Write a file with the message", "capability": "filesystem", "method": "write", "params": {"path": "/tmp/alterego-test-output.txt", "content": "Mission: ' + user[:80] + '"}}]}'
                }
            # If we're being asked for intent, return one
            if "extract the user's intent" in params.get("system", ""):
                return {"content": "Write the user's message to a file."}
            # Default: echo
            return {"content": f"echo: {user}"}
        raise ValueError(method)


@pytest.mark.asyncio
async def test_end_to_end_mission_writes_file():
    """A user mission flows through:
    ChiefOfStaff → MissionEngine → DecisionEngine → Planner → Filesystem plugin
    """
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "output.txt"

        # 1. Kernel infrastructure
        memory = SQLiteMemory(Path(tmp) / "test.db")
        bus = InProcessEventBus()

        # 2. Plugins — manually wire filesystem + mock LLM
        pm = PluginManager()
        from alterego.plugins.filesystem import FilesystemPlugin
        fs_plugin = FilesystemPlugin()
        await fs_plugin.initialize()
        pm._plugins["filesystem"] = fs_plugin
        pm._by_capability["filesystem"] = ["filesystem"]

        llm_plugin = EchoLLMPlugin()
        await llm_plugin.initialize()
        pm._plugins["echo_llm"] = llm_plugin
        pm._by_capability["llm.chat"] = ["echo_llm"]

        # 3. Capabilities
        cap_reg = CapabilityRegistry()
        cap_reg.register(CapabilitySpec(name="filesystem", description="File ops"))
        cap_reg.register(CapabilitySpec(name="llm.chat", description="LLM chat"))

        # 4. Engines
        planner = Planner(cap_reg, llm_plugin)
        decision = DecisionEngine(memory, planner, llm_plugin)
        mission_engine = MissionEngine(memory, bus, decision, pm)
        cos = ChiefOfStaff(mission_engine, memory, bus)

        # Override the output path via the mission objective (the mock LLM uses /tmp/alterego-test-output.txt)
        # Simpler: ask for something, expect /tmp/alterego-test-output.txt
        expected_path = Path("/tmp/alterego-test-output.txt")
        if expected_path.exists():
            expected_path.unlink()

        response = await cos.chat("Hello ALTEREGO, this is a test")

        # File should have been written
        assert expected_path.exists()
        content = expected_path.read_text()
        assert "Mission:" in content
        assert "Hello ALTEREGO" in content

        # Response should mention mission completion
        assert "Mission terminée" in response or "✓" in response

        # Cleanup
        expected_path.unlink(missing_ok=True)
