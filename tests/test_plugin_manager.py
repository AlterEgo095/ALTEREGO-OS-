"""Tests for the Plugin Manager."""
import pytest

from alterego.kernel.plugin_manager import PluginManager
from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec


class FakePluginA(BasePlugin):
    spec = BridgeSpec(name="a", capabilities=["github"])
    plugin_spec = PluginSpec(name="a", capabilities=["github"], priority=20)

    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["x"]
    async def call(self, method, params): return {"from": "a"}


class FakePluginB(BasePlugin):
    """Higher-priority plugin for the same capability."""
    spec = BridgeSpec(name="b", capabilities=["github"])
    plugin_spec = PluginSpec(name="b", capabilities=["github"], priority=5)

    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["x"]
    async def call(self, method, params): return {"from": "b"}


def test_best_for_picks_highest_priority():
    pm = PluginManager()
    # Manually register plugins (skip entry-points discovery)
    pm._plugins["a"] = FakePluginA()
    pm._plugins["b"] = FakePluginB()
    pm._by_capability["github"] = ["a", "b"]
    pm._by_capability["github"].sort(key=lambda n: pm._plugins[n].plugin_spec.priority)

    best = pm.best_for("github")
    assert best is not None
    assert best.plugin_spec.name == "b"  # priority 5 < 20


def test_best_for_returns_none_when_no_plugin():
    pm = PluginManager()
    assert pm.best_for("nonexistent") is None


def test_list_plugins():
    pm = PluginManager()
    pm._plugins["a"] = FakePluginA()
    pm._plugins["b"] = FakePluginB()
    assert sorted(pm.list_plugins()) == ["a", "b"]


def test_list_capabilities():
    pm = PluginManager()
    pm._plugins["a"] = FakePluginA()
    pm._by_capability["github"] = ["a"]
    assert "github" in pm.list_capabilities()
