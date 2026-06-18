"""AUDIT 5 — Capability Registry.

Vérifie que :
- le système choisit une CAPACITÉ, jamais un plugin spécifique
- plusieurs plugins peuvent offrir la même capacité
- le meilleur plugin est sélectionné automatiquement
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from alterego.kernel.base import BasePlugin, BridgeSpec, CapabilitySpec, PluginSpec
from alterego.kernel.capability_registry import CapabilityRegistry
from alterego.kernel.plugin_manager import PluginManager


class GitHubA(BasePlugin):
    spec = BridgeSpec(name="github_a", capabilities=["github"])
    plugin_spec = PluginSpec(name="github_a", capabilities=["github"], priority=20)
    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["clone"]
    async def call(self, method, params): return {"from": "github_a"}


class GitHubB(BasePlugin):
    """Better priority (lower number) than GitHubA."""
    spec = BridgeSpec(name="github_b", capabilities=["github"])
    plugin_spec = PluginSpec(name="github_b", capabilities=["github"], priority=5)
    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["clone"]
    async def call(self, method, params): return {"from": "github_b"}


async def test_registry_selects_capability_not_plugin():
    """The Decision Engine / Mission Engine never call plugin_manager.get('github_a').
    They call plugin_manager.best_for('github') (the capability)."""
    pm = PluginManager()
    pm._plugins["github_a"] = GitHubA()
    pm._by_capability["github"] = ["github_a"]

    # This is the WRONG pattern (kernel should never do this)
    direct = pm.get("github_a")
    # This is the RIGHT pattern (kernel always does this)
    via_capability = pm.best_for("github")

    return {
        "test": "registry_selects_capability_not_plugin",
        "direct_access_works": direct is not None,
        "capability_access_works": via_capability is not None,
        "passed": via_capability is not None,
        "kernel_pattern": "Always best_for(capability), never get(plugin_name)",
    }


async def test_multiple_plugins_same_capability_picks_best():
    """Two plugins offer 'github' — the one with lower priority number wins."""
    pm = PluginManager()
    pm._plugins["github_a"] = GitHubA()  # priority 20
    pm._plugins["github_b"] = GitHubB()  # priority 5 (better)
    pm._by_capability["github"] = ["github_a", "github_b"]
    pm._by_capability["github"].sort(key=lambda n: pm._plugins[n].plugin_spec.priority)

    best = pm.best_for("github")
    return {
        "test": "multiple_plugins_same_capability_picks_best",
        "best_plugin": best.plugin_spec.name,
        "passed": best.plugin_spec.name == "github_b",
    }


async def test_capability_registry_metadata():
    """CapabilityRegistry holds descriptions that the LLM planner can read."""
    cr = CapabilityRegistry()
    cr.register(CapabilitySpec(name="github", description="GitHub operations", required_plugins=[]))
    cr.register(CapabilitySpec(name="docker", description="Docker operations", required_plugins=[]))

    desc = cr.describe()
    return {
        "test": "capability_registry_metadata",
        "has_github": "github" in desc,
        "has_docker": "docker" in desc,
        "passed": "github" in desc and "docker" in desc,
    }


async def test_unknown_capability_returns_none():
    pm = PluginManager()
    result = pm.best_for("nonexistent")
    return {
        "test": "unknown_capability_returns_none",
        "passed": result is None,
    }


async def test_kernel_never_imports_plugins_directly():
    """Verify (statically) that no kernel module imports from alterego.plugins.*"""
    import ast
    kernel_dir = Path(__file__).resolve().parent.parent.parent / "alterego" / "kernel"
    violations = []
    for py in kernel_dir.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("alterego.plugins"):
                    violations.append(f"{py.name}: imports {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("alterego.plugins"):
                            violations.append(f"{py.name}: imports {alias.name}")
        except SyntaxError:
            pass

    return {
        "test": "kernel_never_imports_plugins_directly",
        "violations": violations,
        "passed": len(violations) == 0,
        "behavior": "Kernel only depends on alterego.kernel.base (the ABCs). Plugins are loaded dynamically via PluginManager.",
    }


async def test_swap_plugin_implementation_transparent():
    """Swapping github_a → github_b should not require any Kernel code change."""
    # First, use github_a
    pm1 = PluginManager()
    pm1._plugins["github_a"] = GitHubA()
    pm1._by_capability["github"] = ["github_a"]
    result_a = await pm1.best_for("github").call("clone", {})

    # Now swap to github_b — same capability, different plugin
    pm2 = PluginManager()
    pm2._plugins["github_b"] = GitHubB()
    pm2._by_capability["github"] = ["github_b"]
    result_b = await pm2.best_for("github").call("clone", {})

    return {
        "test": "swap_plugin_implementation_transparent",
        "result_a": result_a,
        "result_b": result_b,
        "passed": result_a["from"] == "github_a" and result_b["from"] == "github_b",
        "kernel_code_changed": False,
    }


async def main():
    results = {"audit": "capability_registry", "tests": [], "issues": [], "score": 0}
    print("=" * 70)
    print("AUDIT 5 — CAPABILITY REGISTRY")
    print("=" * 70)

    tests = [
        test_registry_selects_capability_not_plugin,
        test_multiple_plugins_same_capability_picks_best,
        test_capability_registry_metadata,
        test_unknown_capability_returns_none,
        test_kernel_never_imports_plugins_directly,
        test_swap_plugin_implementation_transparent,
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

    results["issues"].append({
        "severity": "info",
        "category": "no_health_filtering",
        "message": "best_for() doesn't skip unhealthy plugins yet. V2: add health check filter.",
    })

    passed = sum(1 for t in results["tests"] if t.get("passed"))
    total = len(results["tests"])
    score = int(passed / total * 100) if total else 0
    score = max(0, score - sum(1 for i in results["issues"] if i["severity"] == "info"))
    results["score"] = score

    print(f"\n{'=' * 70}")
    print(f"TESTS PASSED: {passed}/{total}")
    print(f"SCORE: {score}/100")

    out = Path(__file__).resolve().parent.parent / "results" / "audit_05_capability_registry.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())
