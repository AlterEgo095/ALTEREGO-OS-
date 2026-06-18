"""Tests for the Planner."""
import json
from typing import Any

import pytest

from alterego.kernel.base import Mission
from alterego.kernel.capability_registry import CapabilityRegistry
from alterego.kernel.base import CapabilitySpec
from alterego.kernel.planner import Planner


class FakeLLM:
    """Fake LLM plugin that returns a canned JSON plan."""

    def __init__(self, plan: dict[str, Any]):
        self.plan = plan

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        if method == "chat":
            return {"content": json.dumps(self.plan)}
        raise ValueError(method)


@pytest.mark.asyncio
async def test_planner_produces_tasks():
    cap_reg = CapabilityRegistry()
    cap_reg.register(CapabilitySpec(name="github", description="GitHub ops"))
    cap_reg.register(CapabilitySpec(name="llm.chat", description="LLM chat"))

    fake_llm = FakeLLM({
        "tasks": [
            {"step": 1, "description": "Get repo info", "capability": "github", "method": "get_repo_info", "params": {"repo": "vercel/next.js"}},
            {"step": 2, "description": "Summarize", "capability": "llm.chat", "method": "chat", "params": {"user": "summarize"}},
        ]
    })
    planner = Planner(cap_reg, fake_llm)

    mission = Mission(id="m1", objective="Tell me about vercel/next.js")
    tasks = await planner.plan(mission)

    assert len(tasks) == 2
    assert tasks[0].capability == "github"
    assert tasks[0].method == "get_repo_info"
    assert tasks[1].capability == "llm.chat"


@pytest.mark.asyncio
async def test_planner_fallback_on_invalid_json():
    cap_reg = CapabilityRegistry()
    cap_reg.register(CapabilitySpec(name="llm.chat", description="LLM chat"))

    # LLM returns junk
    fake_llm = FakeLLM({"not_a_valid_plan": True})  # Will be json.dumps'd into something with no "tasks" key
    planner = Planner(cap_reg, fake_llm)

    mission = Mission(id="m2", objective="hi")
    tasks = await planner.plan(mission)
    # Falls back to a single llm.chat task
    assert len(tasks) == 1
    assert tasks[0].capability == "llm.chat"


@pytest.mark.asyncio
async def test_planner_fallback_on_llm_error():
    cap_reg = CapabilityRegistry()
    cap_reg.register(CapabilitySpec(name="llm.chat", description="LLM chat"))

    class BrokenLLM:
        async def call(self, method, params):
            raise RuntimeError("LLM down")

    planner = Planner(cap_reg, BrokenLLM())
    mission = Mission(id="m3", objective="hi")
    tasks = await planner.plan(mission)
    assert len(tasks) == 1
    assert tasks[0].capability == "llm.chat"
