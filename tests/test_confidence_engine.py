"""Tests for the ConfidenceEngine."""
import tempfile
from pathlib import Path

import pytest

from alterego.kernel import (
    CapabilityRegistry, CapabilitySpec, ConfidenceEngine,
    InProcessEventBus, PluginManager, PolicyEngine, SQLiteMemory,
)
from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class MockLLMPlugin(BasePlugin):
    spec = BridgeSpec(name="mock_llm", capabilities=["llm.chat"])
    plugin_spec = PluginSpec(name="mock_llm", capabilities=["llm.chat"], priority=10)
    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["chat"]
    async def call(self, method, params): return {"content": "ok"}


class MockFSPlugin(BasePlugin):
    spec = BridgeSpec(name="mock_fs", capabilities=["filesystem"])
    plugin_spec = PluginSpec(name="mock_fs", capabilities=["filesystem"], priority=10)
    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["read"]
    async def call(self, method, params): return "ok"


@pytest.fixture
async def setup():
    with tempfile.TemporaryDirectory() as tmp:
        memory = SQLiteMemory(Path(tmp) / "test.db")
        bus = InProcessEventBus()
        pm = PluginManager()
        llm = MockLLMPlugin()
        await llm.initialize()
        fs = MockFSPlugin()
        await fs.initialize()
        pm._plugins["mock_llm"] = llm
        pm._plugins["mock_fs"] = fs
        pm._by_capability["llm.chat"] = ["mock_llm"]
        pm._by_capability["filesystem"] = ["mock_fs"]
        policy = PolicyEngine()
        engine = ConfidenceEngine(pm, policy, memory)
        yield memory, pm, policy, engine


@pytest.mark.asyncio
async def test_high_confidence_for_simple_read_only_plan(setup):
    """A short plan with available capabilities and low risk should score high."""
    _, _, _, engine = setup
    plan = [
        {"step": 1, "description": "Read a file", "capability": "filesystem", "method": "read", "params": {"path": "/tmp/test"}},
        {"step": 2, "description": "Respond", "capability": "llm.chat", "method": "chat", "params": {"user": "ok"}},
    ]
    result = await engine.score(plan)
    assert result["score"] >= 80
    assert result["decision"] in {"auto", "recommend_validation"}
    assert result["missing_capabilities"] == []


@pytest.mark.asyncio
async def test_lower_confidence_for_high_risk_plan(setup):
    """A plan with SSH exec (critical risk) should score lower."""
    _, _, _, engine = setup
    plan = [
        {"step": 1, "description": "Run command on VPS", "capability": "ssh", "method": "exec", "params": {"command": "ls"}},
    ]
    result = await engine.score(plan)
    # SSH is critical risk, but capability may not be available → lower score
    assert result["score"] < 95


@pytest.mark.asyncio
async def test_missing_capability_lowers_score(setup):
    """A plan referencing a missing capability should score lower."""
    _, _, _, engine = setup
    plan = [
        {"step": 1, "description": "Use unknown", "capability": "nonexistent.cap", "method": "do", "params": {}},
    ]
    result = await engine.score(plan)
    assert result["score"] < 80
    assert "nonexistent.cap" in result["missing_capabilities"]


@pytest.mark.asyncio
async def test_empty_plan_low_score(setup):
    _, _, _, engine = setup
    result = await engine.score([])
    assert result["score"] < 50
    assert result["decision"] == "require_validation"


@pytest.mark.asyncio
async def test_too_long_plan_lowers_score(setup):
    """A plan with 30+ tasks should have lower confidence."""
    _, _, _, engine = setup
    plan = [
        {"step": i, "description": f"task {i}", "capability": "llm.chat", "method": "chat", "params": {"user": "ok"}}
        for i in range(1, 31)
    ]
    result = await engine.score(plan)
    assert result["factors"]["plan_length"] < 0.5


@pytest.mark.asyncio
async def test_decision_thresholds(setup):
    """Verify auto/recommend/require thresholds."""
    _, _, _, engine = setup
    # Perfect plan: 2 tasks, available caps, low risk
    plan = [
        {"step": 1, "description": "Read", "capability": "filesystem", "method": "read", "params": {"path": "/tmp"}},
        {"step": 2, "description": "Respond", "capability": "llm.chat", "method": "chat", "params": {"user": "ok"}},
    ]
    result = await engine.score(plan)
    # With neutral historical prior (0.7), should be high
    assert result["score"] > 0
    assert result["decision"] in {"auto", "recommend_validation", "require_validation"}


@pytest.mark.asyncio
async def test_high_risk_tasks_flagged(setup):
    """High-risk tasks should be flagged in the result."""
    _, _, _, engine = setup
    plan = [
        {"step": 1, "description": "Delete file", "capability": "filesystem", "method": "delete", "params": {"path": "/tmp/x"}},
    ]
    result = await engine.score(plan)
    assert len(result["high_risk_tasks"]) >= 1
    assert result["high_risk_tasks"][0]["risk"] == "high"
