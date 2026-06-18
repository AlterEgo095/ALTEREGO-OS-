"""Tests for the CapabilityRegistry."""
import pytest

from alterego.kernel.capability_registry import CapabilityRegistry
from alterego.kernel.base import CapabilitySpec


def test_register_and_get():
    reg = CapabilityRegistry()
    cap = CapabilitySpec(name="github", description="GitHub ops", required_plugins=["github"])
    reg.register(cap)
    assert reg.get("github") is cap
    assert reg.exists("github")


def test_get_nonexistent():
    reg = CapabilityRegistry()
    assert reg.get("nope") is None
    assert not reg.exists("nope")


def test_list():
    reg = CapabilityRegistry()
    reg.register(CapabilitySpec(name="github", description=""))
    reg.register(CapabilitySpec(name="docker", description=""))
    caps = reg.list()
    assert len(caps) == 2
    names = [c.name for c in caps]
    assert "github" in names
    assert "docker" in names


def test_describe_for_llm():
    reg = CapabilityRegistry()
    reg.register(CapabilitySpec(name="github", description="GitHub operations", required_plugins=["github"]))
    reg.register(CapabilitySpec(name="llm.chat", description="LLM chat", required_plugins=["llm"]))
    desc = reg.describe()
    assert "github" in desc
    assert "GitHub operations" in desc
    assert "llm.chat" in desc
    assert "LLM chat" in desc
