"""Tests for the Kernel base contracts."""
import pytest

from alterego.kernel.base import (
    BaseBridge, BasePlugin, BaseCapability,
    BridgeSpec, PluginSpec, CapabilitySpec,
    Mission, MissionStatus, Event,
)


def test_bridge_spec_defaults():
    s = BridgeSpec(name="test")
    assert s.name == "test"
    assert s.version == "0.1.0"
    assert s.capabilities == []


def test_plugin_spec():
    s = PluginSpec(name="github", capabilities=["github"], priority=10)
    assert s.name == "github"
    assert s.priority == 10


def test_capability_spec():
    c = CapabilitySpec(name="github", description="GitHub ops")
    assert c.name == "github"
    assert c.required_plugins == []


def test_mission_creation():
    m = Mission(id="abc", objective="test objective")
    assert m.status == MissionStatus.CREATED
    assert m.result is None
    assert m.error is None


def test_mission_status_enum():
    assert MissionStatus.CREATED == "created"
    assert MissionStatus.COMPLETED == "completed"
    assert MissionStatus.FAILED == "failed"


def test_event_creation():
    e = Event(subject="mission.created", payload={"id": "abc"})
    assert e.subject == "mission.created"
    assert e.payload["id"] == "abc"
    assert e.source == ""


def test_base_bridge_is_abstract():
    with pytest.raises(TypeError):
        BaseBridge()


def test_base_plugin_is_abstract():
    with pytest.raises(TypeError):
        BasePlugin()
