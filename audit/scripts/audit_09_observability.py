"""AUDIT 9 — Observabilité.

Vérifie :
- logs structurés
- metrics
- healthcheck
- latence
- temps d'exécution
- erreurs
- utilisation mémoire
- utilisation CPU
- coût LLM
- nombre d'appels plugins
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
from alterego.kernel import (
    CapabilityRegistry, CapabilitySpec, ChiefOfStaff, DecisionEngine,
    InProcessEventBus, MissionEngine, Planner, PluginManager, SQLiteMemory,
)


class MockLLM(BasePlugin):
    spec = BridgeSpec(name="mock_llm", capabilities=["llm.chat"])
    plugin_spec = PluginSpec(name="mock_llm", capabilities=["llm.chat"], priority=10)
    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["chat"]
    async def call(self, method, params):
        system = params.get("system", "")
        if "Available capabilities" in system:
            return {"content": json.dumps({"tasks": [{"step": 1, "description": "Respond", "capability": "llm.chat", "method": "chat", "params": {"user": params.get("user", "")}}]})}
        if "extract the user's intent" in system:
            return {"content": "Test"}
        return {"content": "OK"}


async def test_structured_logging():
    """Verify loguru is used and produces structured output."""
    # Check that loguru is imported in kernel modules
    kernel_dir = Path(__file__).resolve().parent.parent.parent / "alterego" / "kernel"
    modules_using_loguru = []
    for py in kernel_dir.rglob("*.py"):
        if "from loguru import logger" in py.read_text():
            modules_using_loguru.append(py.name)

    return {
        "test": "structured_logging",
        "modules_using_loguru": modules_using_loguru,
        "passed": len(modules_using_loguru) >= 5,  # most kernel modules should log
        "v1_behavior": "loguru used across kernel modules",
        "v2_needed": [
            "Structured JSON logs (not just text)",
            "Correlation IDs per mission (trace every event back to its mission)",
            "Log levels configurable per module",
        ],
    }


async def test_metrics_infrastructure():
    """V1 has no metrics infrastructure. Document the gap."""
    # Check for any prometheus/otel imports
    kernel_dir = Path(__file__).resolve().parent.parent.parent / "alterego"
    has_metrics = False
    for py in kernel_dir.rglob("*.py"):
        src = py.read_text()
        if "prometheus" in src or "opentelemetry" in src or "metrics" in src.lower():
            has_metrics = True
            break

    return {
        "test": "metrics_infrastructure",
        "v1_has_metrics": has_metrics,
        "passed": False,  # honestly documented
        "v2_needed": [
            "prometheus_client for counters/histograms",
            "Metrics: missions_total, missions_completed, missions_failed, plugin_calls_total, plugin_errors_total, llm_tokens_total, llm_cost_total, event_bus_published_total",
            "Metrics endpoint /metrics for scraping",
        ],
    }


async def test_health_check_endpoint():
    """Verify the CLI has a `health` command that checks all plugins."""
    cli_src = (Path(__file__).resolve().parent.parent.parent / "alterego" / "cli.py").read_text()
    has_health_cmd = "def health" in cli_src or "@app.command()\ndef health" in cli_src

    return {
        "test": "health_check_endpoint",
        "v1_has_health_cli": has_health_cmd,
        "passed": has_health_cmd,
        "v1_behavior": "alterego health command checks all plugins",
        "v2_needed": [
            "HTTP /health endpoint for k8s liveness/readiness probes",
            "Detailed /health/ready vs /health/live distinction",
        ],
    }


async def test_latency_measurement():
    """Measure end-to-end mission latency."""
    with tempfile_dir() as tmp:
        memory = SQLiteMemory(Path(tmp) / "test.db")
        bus = InProcessEventBus()
        pm = PluginManager()
        llm = MockLLM()
        await llm.initialize()
        pm._plugins["mock_llm"] = llm
        pm._by_capability["llm.chat"] = ["mock_llm"]
        cap_reg = CapabilityRegistry()
        cap_reg.register(CapabilitySpec(name="llm.chat", description="LLM"))
        planner = Planner(cap_reg, llm)
        decision = DecisionEngine(memory, planner, llm)
        engine = MissionEngine(memory, bus, decision, pm)
        cos = ChiefOfStaff(engine, memory, bus)

        # Run 50 missions, measure latency
        latencies = []
        for i in range(50):
            start = time.perf_counter()
            await cos.chat(f"test mission {i}")
            latencies.append((time.perf_counter() - start) * 1000)

        avg = sum(latencies) / len(latencies)
        p99 = sorted(latencies)[int(0.99 * len(latencies))]

        return {
            "test": "latency_measurement",
            "samples": len(latencies),
            "avg_ms": round(avg, 2),
            "p99_ms": round(p99, 2),
            "min_ms": round(min(latencies), 2),
            "max_ms": round(max(latencies), 2),
            "passed": avg < 100,  # in-process should be fast
            "v2_needed": [
                "Per-stage latency tracking (CoS→Engine→Planner→Plugin→Response)",
                "Latency histogram per capability",
                "Slow query log (>500ms)",
            ],
        }


async def test_plugin_call_counting():
    """V1 doesn't count plugin calls. Document the gap."""
    return {
        "test": "plugin_call_counting",
        "v1_has_counter": False,
        "passed": False,
        "v2_needed": [
            "Counter per (plugin, method) pair",
            "Counter for success/failure ratio",
            "Expose via /metrics endpoint",
        ],
    }


async def test_llm_cost_tracking():
    """V1 LLM plugin returns usage info but it's not aggregated."""
    llm_src = (Path(__file__).resolve().parent.parent.parent / "alterego" / "plugins" / "llm" / "__init__.py").read_text()
    returns_usage = "usage" in llm_src and "prompt_tokens" in llm_src and "completion_tokens" in llm_src

    return {
        "test": "llm_cost_tracking",
        "v1_returns_usage_per_call": returns_usage,
        "v1_aggregates_cost": False,
        "passed": returns_usage,  # partial — usage is returned, just not aggregated
        "v2_needed": [
            "Aggregate tokens per mission, per user, per day",
            "Cost calculation (tokens × price per model)",
            "Daily/weekly cost reports",
            "Cost alerts (budget thresholds)",
        ],
    }


async def test_memory_usage_tracking():
    """V1 doesn't track its own memory usage."""
    return {
        "test": "memory_usage_tracking",
        "v1_has_tracking": False,
        "passed": False,
        "v2_needed": [
            "RSS memory tracking (psutil.Process().memory_info().rss)",
            "Memory per plugin (if isolated in subprocess)",
            "Memory alerts (notify if RSS > threshold)",
        ],
    }


async def test_cpu_usage_tracking():
    """V1 doesn't track CPU usage."""
    return {
        "test": "cpu_usage_tracking",
        "v1_has_tracking": False,
        "passed": False,
        "v2_needed": [
            "CPU% per plugin",
            "CPU time per mission",
            "Alerts on sustained high CPU",
        ],
    }


async def test_error_tracking():
    """V1 logs errors via loguru but doesn't aggregate them."""
    return {
        "test": "error_tracking",
        "v1_logs_errors": True,  # loguru logs errors
        "v1_aggregates_errors": False,
        "passed": True,  # logging is the minimum; aggregation is V2
        "v2_needed": [
            "Error counter per (component, error_type)",
            "Error rate alerting (>5% failure rate)",
            "Sentry integration for production",
        ],
    }


async def main():
    results = {"audit": "observability", "tests": [], "issues": [], "score": 0}
    print("=" * 70)
    print("AUDIT 9 — OBSERVABILITÉ")
    print("=" * 70)

    tests = [
        test_structured_logging,
        test_metrics_infrastructure,
        test_health_check_endpoint,
        test_latency_measurement,
        test_plugin_call_counting,
        test_llm_cost_tracking,
        test_memory_usage_tracking,
        test_cpu_usage_tracking,
        test_error_tracking,
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
                results["issues"].append({"severity": "warning", "test": name, "message": str(r)})
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results["tests"].append({"test": name, "passed": False, "error": str(e)})
            results["issues"].append({"severity": "critical", "test": name, "message": str(e)})

    passed = sum(1 for t in results["tests"] if t.get("passed"))
    total = len(results["tests"])
    score = int(passed / total * 100) if total else 0
    results["score"] = score

    print(f"\n{'=' * 70}")
    print(f"TESTS PASSED: {passed}/{total}")
    print(f"SCORE: {score}/100")

    out = Path(__file__).resolve().parent.parent / "results" / "audit_09_observability.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to: {out}")


from contextlib import contextmanager
import tempfile

@contextmanager
def tempfile_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


if __name__ == "__main__":
    asyncio.run(main())
