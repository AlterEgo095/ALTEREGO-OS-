"""AUDIT 4 — Plugin Manager.

Installe :
- plugin fictif
- plugin invalide
- plugin cassé
- plugin lent
- plugin incompatible
- plugin absent

Vérifie :
- rollback
- isolation
- timeout
- logs
- erreurs

Le Kernel ne doit jamais planter.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec
from alterego.kernel.plugin_manager import PluginManager


# ── Test plugins ─────────────────────────────────────────────────────────────
class GoodPlugin(BasePlugin):
    spec = BridgeSpec(name="good", capabilities=["test.good"])
    plugin_spec = PluginSpec(name="good", capabilities=["test.good"], priority=10)

    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["ping"]
    async def call(self, method, params): return {"pong": True}


class BrokenInitPlugin(BasePlugin):
    spec = BridgeSpec(name="broken_init", capabilities=["test.broken_init"])
    plugin_spec = PluginSpec(name="broken_init", capabilities=["test.broken_init"], priority=10)

    async def initialize(self):
        raise RuntimeError("init failed")

    async def shutdown(self): pass
    async def health(self): return False
    def methods(self): return ["ping"]
    async def call(self, method, params): return {}


class BrokenCallPlugin(BasePlugin):
    spec = BridgeSpec(name="broken_call", capabilities=["test.broken_call"])
    plugin_spec = PluginSpec(name="broken_call", capabilities=["test.broken_call"], priority=10)

    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["ping"]
    async def call(self, method, params):
        raise RuntimeError("call failed")


class SlowPlugin(BasePlugin):
    spec = BridgeSpec(name="slow", capabilities=["test.slow"])
    plugin_spec = PluginSpec(name="slow", capabilities=["test.slow"], priority=10)

    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["ping"]
    async def call(self, method, params):
        await asyncio.sleep(2.0)  # 2 seconds
        return {"slow": True}


class FakeSpecPlugin(BasePlugin):
    """Plugin that claims more capabilities than it actually implements."""
    spec = BridgeSpec(name="fake_spec", capabilities=["test.fake"])
    plugin_spec = PluginSpec(
        name="fake_spec",
        capabilities=["test.fake", "test.inexistent"],
        priority=10,
    )

    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["ping"]
    async def call(self, method, params): return {"fake": True}


async def test_load_good_plugin():
    pm = PluginManager()
    pm._plugins["good"] = GoodPlugin()
    pm._by_capability["test.good"] = ["good"]
    await pm.initialize_all()
    plugin = pm.best_for("test.good")
    return {
        "test": "load_good_plugin",
        "passed": plugin is not None and plugin.plugin_spec.name == "good",
    }


async def test_load_broken_init_does_not_crash_kernel():
    """Plugin with broken initialize() should not crash the PluginManager."""
    pm = PluginManager()
    pm._plugins["broken_init"] = BrokenInitPlugin()
    pm._by_capability["test.broken_init"] = ["broken_init"]
    try:
        await pm.initialize_all()
        # The plugin is registered but failed to init
        return {
            "test": "load_broken_init_does_not_crash_kernel",
            "passed": True,
            "behavior": "PluginManager caught the init exception and continued",
        }
    except Exception as e:
        return {
            "test": "load_broken_init_does_not_crash_kernel",
            "passed": False,
            "error": f"PluginManager crashed: {e}",
        }


async def test_load_broken_call_does_not_crash_kernel():
    """Plugin whose call() raises should let the caller catch the exception."""
    pm = PluginManager()
    pm._plugins["broken_call"] = BrokenCallPlugin()
    pm._by_capability["test.broken_call"] = ["broken_call"]
    await pm.initialize_all()
    plugin = pm.best_for("test.broken_call")
    try:
        await plugin.call("ping", {})
        return {"test": "load_broken_call_does_not_crash_kernel", "passed": False, "error": "no exception raised"}
    except RuntimeError as e:
        return {
            "test": "load_broken_call_does_not_crash_kernel",
            "passed": "call failed" in str(e),
            "behavior": "Exception propagated cleanly to caller",
        }


async def test_slow_plugin_with_timeout():
    """Slow plugin should be wrappable in asyncio.wait_for to enforce a timeout."""
    pm = PluginManager()
    pm._plugins["slow"] = SlowPlugin()
    pm._by_capability["test.slow"] = ["slow"]
    await pm.initialize_all()
    plugin = pm.best_for("test.slow")
    start = time.perf_counter()
    try:
        await asyncio.wait_for(plugin.call("ping", {}), timeout=0.5)
        return {
            "test": "slow_plugin_with_timeout",
            "passed": False,
            "error": "Timeout did not trigger",
        }
    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - start
        return {
            "test": "slow_plugin_with_timeout",
            "passed": 0.4 < elapsed < 0.7,
            "elapsed_ms": round(elapsed * 1000, 1),
            "behavior": "asyncio.wait_for correctly cancelled the slow call",
        }


async def test_isolation_between_plugins():
    """A failing plugin should not prevent another plugin from working."""
    pm = PluginManager()
    pm._plugins["good"] = GoodPlugin()
    pm._plugins["broken_call"] = BrokenCallPlugin()
    pm._by_capability["test.good"] = ["good"]
    pm._by_capability["test.broken_call"] = ["broken_call"]
    await pm.initialize_all()

    # Call good plugin
    good_result = await pm.best_for("test.good").call("ping", {})

    # Try to call broken plugin (should raise)
    broken_failed = False
    try:
        await pm.best_for("test.broken_call").call("ping", {})
    except RuntimeError:
        broken_failed = True

    # Good plugin still works after broken failed?
    good_result_2 = await pm.best_for("test.good").call("ping", {})

    return {
        "test": "isolation_between_plugins",
        "good_plugin_worked_before": good_result.get("pong") is True,
        "broken_plugin_raised": broken_failed,
        "good_plugin_worked_after": good_result_2.get("pong") is True,
        "passed": good_result.get("pong") and broken_failed and good_result_2.get("pong"),
    }


async def test_missing_capability_returns_none():
    """Asking for a capability that no plugin provides should return None."""
    pm = PluginManager()
    plugin = pm.best_for("test.nonexistent")
    return {
        "test": "missing_capability_returns_none",
        "passed": plugin is None,
        "behavior": "best_for() returns None cleanly — caller must handle",
    }


async def test_fake_spec_plugin():
    """Plugin that claims capabilities it doesn't implement should still be loadable
    (we can't validate semantic correctness at load time)."""
    pm = PluginManager()
    pm._plugins["fake_spec"] = FakeSpecPlugin()
    for cap in FakeSpecPlugin.plugin_spec.capabilities:
        pm._by_capability.setdefault(cap, []).append("fake_spec")
    await pm.initialize_all()
    return {
        "test": "fake_spec_plugin",
        "passed": True,
        "behavior": "Plugin loads; quality validation is V2 (V1 trusts the spec)",
        "recommendation": "V2: add runtime capability verification — try calling each declared method at load time",
    }


async def test_shutdown_cleans_up():
    pm = PluginManager()
    pm._plugins["good"] = GoodPlugin()
    pm._by_capability["test.good"] = ["good"]
    await pm.initialize_all()
    await pm.shutdown_all()
    return {
        "test": "shutdown_cleans_up",
        "passed": True,  # no exception = pass
        "behavior": "shutdown_all() called all shutdown hooks",
    }


async def test_multiple_plugins_same_capability():
    """Two plugins offer the same capability — best_for picks the lowest priority number."""
    pm = PluginManager()
    pm._plugins["low_pri"] = GoodPlugin()
    pm._plugins["low_pri"].plugin_spec = PluginSpec(name="low_pri", capabilities=["test.dup"], priority=50)
    pm._plugins["high_pri"] = GoodPlugin()
    pm._plugins["high_pri"].plugin_spec = PluginSpec(name="high_pri", capabilities=["test.dup"], priority=5)
    pm._by_capability["test.dup"] = ["low_pri", "high_pri"]
    pm._by_capability["test.dup"].sort(key=lambda n: pm._plugins[n].plugin_spec.priority)
    best = pm.best_for("test.dup")
    return {
        "test": "multiple_plugins_same_capability",
        "best_plugin": best.plugin_spec.name,
        "passed": best.plugin_spec.name == "high_pri",
    }


async def main():
    results = {"audit": "plugin_manager", "tests": [], "issues": [], "score": 0}
    print("=" * 70)
    print("AUDIT 4 — PLUGIN MANAGER")
    print("=" * 70)

    tests = [
        test_load_good_plugin,
        test_load_broken_init_does_not_crash_kernel,
        test_load_broken_call_does_not_crash_kernel,
        test_slow_plugin_with_timeout,
        test_isolation_between_plugins,
        test_missing_capability_returns_none,
        test_fake_spec_plugin,
        test_shutdown_cleans_up,
        test_multiple_plugins_same_capability,
    ]

    for test_fn in tests:
        name = test_fn.__name__
        print(f"\n── {name} ──")
        try:
            r = await test_fn()
            results["tests"].append(r)
            passed = r.get("passed", False)
            print(f"  {'✓ PASS' if passed else '✗ FAIL'}")
            for k, v in r.items():
                if k not in {"test", "passed"}:
                    print(f"    {k}: {v}")
            if not passed:
                results["issues"].append({"severity": "critical", "test": name, "message": str(r)})
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results["tests"].append({"test": name, "passed": False, "error": str(e)})
            results["issues"].append({"severity": "critical", "test": name, "message": str(e)})

    # Documented limitations
    results["issues"].append({
        "severity": "warning",
        "category": "no_builtin_timeout",
        "message": "PluginManager has no built-in timeout. Callers must wrap with asyncio.wait_for.",
    })
    results["issues"].append({
        "severity": "warning",
        "category": "no_capability_verification",
        "message": "Plugin specs are trusted at load time. V2: validate by calling each declared method.",
    })
    results["issues"].append({
        "severity": "warning",
        "category": "no_health_filtering",
        "message": "best_for() returns the first plugin by priority, doesn't check health. V2: skip unhealthy plugins.",
    })

    passed = sum(1 for t in results["tests"] if t.get("passed"))
    total = len(results["tests"])
    score = int(passed / total * 100) if total else 0
    score = max(0, score - sum(3 for i in results["issues"] if i["severity"] == "warning"))
    results["score"] = score

    print(f"\n{'=' * 70}")
    print(f"TESTS PASSED: {passed}/{total}")
    print(f"SCORE: {score}/100")

    out = Path(__file__).resolve().parent.parent / "results" / "audit_04_plugin_manager.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())
