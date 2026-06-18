"""Tests for the LearningEngine."""
import tempfile
from pathlib import Path

import pytest

from alterego.kernel import InProcessEventBus, LearningEngine, SQLiteMemory
from alterego.kernel.base import Mission, MissionStatus


@pytest.fixture
async def setup():
    with tempfile.TemporaryDirectory() as tmp:
        memory = SQLiteMemory(Path(tmp) / "test.db")
        bus = InProcessEventBus()
        engine = LearningEngine(memory, bus)
        yield memory, engine


@pytest.mark.asyncio
async def test_record_mission_outcome(setup):
    memory, engine = setup
    mission = Mission(
        id="m1",
        objective="test",
        status=MissionStatus.COMPLETED,
        plan=[
            {"step": 1, "capability": "filesystem", "method": "read"},
            {"step": 2, "capability": "llm.chat", "method": "chat"},
        ],
    )
    await engine.record_mission_outcome(mission)
    records = await memory.query("knowledge")
    assert len(records) == 1
    assert records[0].data["mission_id"] == "m1"
    assert "capability_outcomes" in records[0].data


@pytest.mark.asyncio
async def test_record_user_feedback(setup):
    memory, engine = setup
    await engine.record_user_feedback("m1", "Great work!", 1)
    records = await memory.query("knowledge")
    assert len(records) == 1
    assert records[0].data["type"] == "user_feedback"
    assert records[0].data["rating"] == 1


@pytest.mark.asyncio
async def test_get_capability_stats(setup):
    memory, engine = setup
    # Record 3 missions with different outcomes
    for i, status in enumerate([MissionStatus.COMPLETED, MissionStatus.COMPLETED, MissionStatus.FAILED]):
        mission = Mission(
            id=f"m{i}",
            objective="test",
            status=status,
            plan=[{"step": 1, "capability": "filesystem", "method": "read"}],
        )
        await engine.record_mission_outcome(mission)

    stats = await engine.get_capability_stats()
    assert "filesystem" in stats
    assert stats["filesystem"]["success"] == 2
    assert stats["filesystem"]["failure"] == 1


@pytest.mark.asyncio
async def test_infer_preference(setup):
    memory, engine = setup
    await engine.infer_preference("alice", "language", "fr")
    prefs = await memory.query("preferences", user_id="alice", key="language")
    assert len(prefs) == 1
    assert prefs[0].data["value"] == "fr"
    assert prefs[0].data["inferred"] is True


@pytest.mark.asyncio
async def test_infer_preference_updates_existing(setup):
    memory, engine = setup
    await engine.infer_preference("alice", "language", "fr")
    await engine.infer_preference("alice", "language", "en")
    prefs = await memory.query("preferences", user_id="alice", key="language")
    assert len(prefs) == 1
    assert prefs[0].data["value"] == "en"


@pytest.mark.asyncio
async def test_no_plan_no_record(setup):
    """A mission with no plan should not crash the learning engine."""
    memory, engine = setup
    mission = Mission(id="m1", objective="test", status=MissionStatus.COMPLETED)
    await engine.record_mission_outcome(mission)  # should not raise
    records = await memory.query("knowledge")
    assert len(records) == 0  # nothing recorded
