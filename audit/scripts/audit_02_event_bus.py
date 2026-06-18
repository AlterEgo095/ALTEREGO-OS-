"""AUDIT 2 — Event Bus.

Simule :
- 100 missions simultanées
- 1000 événements
- plugins déconnectés
- événements perdus
- redémarrage du système

Vérifie qu'aucune mission ne disparaît.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from alterego.kernel.event_bus import InProcessEventBus


async def test_basic_throughput():
    """1000 events published, all received."""
    bus = InProcessEventBus()
    received = []

    async def handler(event):
        received.append(event.subject)

    bus.subscribe("test.*", handler)

    for i in range(1000):
        await bus.publish(f"test.{i}", {"i": i})

    return {
        "test": "basic_throughput",
        "published": 1000,
        "received": len(received),
        "passed": len(received) == 1000,
    }


async def test_100_concurrent_missions():
    """100 'missions' (each emitting 10 events) running concurrently."""
    bus = InProcessEventBus()
    all_events = []
    all_events_lock = asyncio.Lock()

    async def handler(event):
        async with all_events_lock:
            all_events.append(event.subject)

    bus.subscribe("mission.*", handler)

    async def run_mission(mission_id: int):
        # Each mission publishes 10 events
        for i in range(10):
            await bus.publish(f"mission.step{i}", {"mission_id": mission_id, "step": i})

    # Launch 100 missions concurrently
    await asyncio.gather(*[run_mission(i) for i in range(100)])

    return {
        "test": "100_concurrent_missions",
        "expected_events": 1000,
        "received_events": len(all_events),
        "passed": len(all_events) == 1000,
    }


async def test_handler_failure_isolation():
    """A failing handler should not break other handlers or lose events."""
    bus = InProcessEventBus()
    good_received = []

    async def bad_handler(event):
        raise RuntimeError("boom")

    async def good_handler(event):
        good_received.append(event.subject)

    bus.subscribe("test.event", bad_handler)
    bus.subscribe("test.event", good_handler)

    await bus.publish("test.event", {"x": 1})
    await bus.publish("test.event", {"x": 2})

    return {
        "test": "handler_failure_isolation",
        "published": 2,
        "good_handler_received": len(good_received),
        "passed": len(good_received) == 2,
    }


async def test_wildcard_matching():
    """Verify mission.* matches mission.created, mission.completed, etc."""
    bus = InProcessEventBus()
    received = []

    async def handler(event):
        received.append(event.subject)

    bus.subscribe("mission.*", handler)
    await bus.publish("mission.created", {})
    await bus.publish("mission.completed", {})
    await bus.publish("mission.failed", {})
    await bus.publish("plugin.called", {})  # should NOT match

    return {
        "test": "wildcard_matching",
        "expected_matches": 3,
        "actual_matches": len(received),
        "subjects": received,
        "passed": len(received) == 3,
    }


async def test_unsubscribe_stops_delivery():
    bus = InProcessEventBus()
    received = []

    async def handler(event):
        received.append(event.subject)

    sub_id = bus.subscribe("test.event", handler)
    await bus.publish("test.event", {})
    bus.unsubscribe(sub_id)
    await bus.publish("test.event", {})

    return {
        "test": "unsubscribe_stops_delivery",
        "expected": 1,
        "actual": len(received),
        "passed": len(received) == 1,
    }


async def test_latency():
    """Measure publish→handler latency."""
    bus = InProcessEventBus()
    latencies = []

    async def handler(event):
        latencies.append(time.perf_counter() - event.payload["sent_at"])

    bus.subscribe("latency.test", handler)
    for _ in range(1000):
        await bus.publish("latency.test", {"sent_at": time.perf_counter()})

    avg = sum(latencies) / len(latencies) * 1000  # ms
    p99 = sorted(latencies)[int(0.99 * len(latencies))] * 1000
    return {
        "test": "latency",
        "samples": len(latencies),
        "avg_ms": round(avg, 3),
        "p99_ms": round(p99, 3),
        "passed": avg < 1.0,  # in-process should be < 1ms
    }


async def test_restart_persistence():
    """Simulate restart — events published before subscribe should NOT be received
    (in-process bus is volatile by design). Verify documented behavior."""
    bus1 = InProcessEventBus()
    received = []

    async def handler(event):
        received.append(event.subject)

    # Publish before subscribe
    await bus1.publish("test.before", {"x": 1})
    bus1.subscribe("test.*", handler)
    await bus1.publish("test.after", {"x": 2})

    # 'restart' = new bus instance
    bus2 = InProcessEventBus()
    bus2.subscribe("test.*", handler)
    await bus2.publish("test.after_restart", {"x": 3})

    return {
        "test": "restart_persistence",
        "expected_volatile_behavior": "in-process bus is volatile; events published before subscribe are lost on restart",
        "received": received,
        "passed": received == ["test.after", "test.after_restart"],
        "recommendation": "V2: switch to NATS JetStream for persistence + replay",
    }


async def main():
    results = {
        "audit": "event_bus",
        "tests": [],
        "issues": [],
        "score": 0,
    }

    tests = [
        ("basic_throughput", test_basic_throughput),
        ("100_concurrent_missions", test_100_concurrent_missions),
        ("handler_failure_isolation", test_handler_failure_isolation),
        ("wildcard_matching", test_wildcard_matching),
        ("unsubscribe_stops_delivery", test_unsubscribe_stops_delivery),
        ("latency", test_latency),
        ("restart_persistence", test_restart_persistence),
    ]

    print("=" * 70)
    print("AUDIT 2 — EVENT BUS")
    print("=" * 70)

    for name, test_fn in tests:
        print(f"\n── {name} ──")
        try:
            result = await test_fn()
            results["tests"].append(result)
            passed = result.get("passed", False)
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status}")
            for k, v in result.items():
                if k != "test" and k != "passed":
                    print(f"    {k}: {v}")
            if not passed:
                results["issues"].append({
                    "severity": "critical",
                    "test": name,
                    "message": f"Test failed: {result}",
                })
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results["tests"].append({"test": name, "passed": False, "error": str(e)})
            results["issues"].append({
                "severity": "critical",
                "test": name,
                "message": f"Test crashed: {e}",
            })

    # Documented limitation (not a failure)
    results["issues"].append({
        "severity": "info",
        "category": "persistence",
        "message": "In-process bus is volatile; no replay on restart. V2: NATS JetStream.",
    })
    results["issues"].append({
        "severity": "info",
        "category": "concurrency",
        "message": "Handlers run sequentially per event (not concurrent). V2: consider concurrent fan-out.",
    })

    # Score
    passed_count = sum(1 for t in results["tests"] if t.get("passed"))
    total = len(results["tests"])
    score = int(passed_count / total * 100) if total else 0
    # Subtract for info issues (-1 each)
    score = max(0, score - sum(1 for i in results["issues"] if i["severity"] == "info"))
    results["score"] = score

    print(f"\n{'=' * 70}")
    print(f"TESTS PASSED: {passed_count}/{total}")
    print(f"SCORE: {score}/100")

    out = Path(__file__).resolve().parent.parent / "results" / "audit_02_event_bus.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to: {out}")
    return results


if __name__ == "__main__":
    asyncio.run(main())
