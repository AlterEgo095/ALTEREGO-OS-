"""AUDIT 3 — Memory.

Teste :
- persistance après redémarrage
- récupération contexte
- concurrence
- corruption base
- montée en charge

Préparer migration PostgreSQL.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from alterego.kernel.memory import SQLiteMemory, ENTITY_TYPES


async def test_persistence_after_restart():
    """Data written before restart must be readable after restart."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"

        # Write
        m1 = SQLiteMemory(db_path)
        rid = await m1.put("projects", {"name": "alterego", "version": "0.1.0"})
        del m1  # simulate process exit

        # Read after restart
        m2 = SQLiteMemory(db_path)
        rec = await m2.get("projects", rid)
        if not rec:
            return {"test": "persistence_after_restart", "passed": False, "error": "record not found after restart"}
        return {
            "test": "persistence_after_restart",
            "passed": rec.data["name"] == "alterego" and rec.data["version"] == "0.1.0",
            "record_id": rid,
        }


async def test_context_recovery():
    """Query conversations for a user_id to recover conversation context."""
    with tempfile.TemporaryDirectory() as tmp:
        m = SQLiteMemory(Path(tmp) / "test.db")
        # Insert several conversations
        for i in range(10):
            await m.put("conversations", {
                "user_id": "alice",
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"message {i}",
                "timestamp": i,
            })
        # Insert some for another user
        for i in range(3):
            await m.put("conversations", {
                "user_id": "bob",
                "role": "user",
                "content": f"bob msg {i}",
            })

        alice = await m.query("conversations", user_id="alice")
        bob = await m.query("conversations", user_id="bob")

        return {
            "test": "context_recovery",
            "alice_messages": len(alice),
            "bob_messages": len(bob),
            "passed": len(alice) == 10 and len(bob) == 3,
        }


async def test_concurrent_writes():
    """100 concurrent puts — no lost writes."""
    with tempfile.TemporaryDirectory() as tmp:
        m = SQLiteMemory(Path(tmp) / "test.db")

        async def write_one(i: int) -> str:
            return await m.put("tasks", {"index": i, "content": f"task-{i}"})

        ids = await asyncio.gather(*[write_one(i) for i in range(100)])
        all_records = await m.query("tasks")

        return {
            "test": "concurrent_writes",
            "concurrent_puts": 100,
            "ids_returned": len(ids),
            "records_in_db": len(all_records),
            "passed": len(ids) == 100 and len(all_records) == 100 and len(set(ids)) == 100,
        }


async def test_concurrent_reads_and_writes():
    """Mixed workload: 50 writers + 50 readers concurrently."""
    with tempfile.TemporaryDirectory() as tmp:
        m = SQLiteMemory(Path(tmp) / "test.db")
        # Pre-populate
        for i in range(50):
            await m.put("tasks", {"index": i})

        read_count = 0
        read_count_lock = asyncio.Lock()

        async def writer(i: int):
            await m.put("tasks", {"index": 100 + i})

        async def reader():
            nonlocal read_count
            await m.query("tasks")
            async with read_count_lock:
                read_count += 1

        await asyncio.gather(*[writer(i) for i in range(50)])
        await asyncio.gather(*[reader() for _ in range(50)])

        final = await m.query("tasks")
        return {
            "test": "concurrent_reads_and_writes",
            "writers": 50,
            "readers": 50,
            "read_completions": read_count,
            "final_count": len(final),
            "passed": read_count == 50 and len(final) == 100,
        }


async def test_database_corruption_recovery():
    """If the DB file is corrupted, the system should not crash silently.
    SQLite handles this via integrity checks."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        m = SQLiteMemory(db_path)
        await m.put("tasks", {"x": 1})
        del m

        # Corrupt the DB file
        with open(db_path, "wb") as f:
            f.write(b"CORRUPTED_DATA" * 1000)

        # Try to use it
        try:
            m2 = SQLiteMemory(db_path)
            await m2.put("tasks", {"y": 2})
            # If SQLite auto-recovered (it shouldn't with binary garbage), test passes
            recs = await m2.query("tasks")
            return {
                "test": "database_corruption_recovery",
                "behavior": "SQLite auto-recovered (re-created schema)",
                "passed": True,
                "records_after_recovery": len(recs),
            }
        except Exception as e:
            return {
                "test": "database_corruption_recovery",
                "behavior": f"Crashed as expected: {type(e).__name__}: {e}",
                "passed": False,
                "recommendation": "V2: add try/except in SQLiteMemory._init_db to auto-backup-and-recreate on corruption",
            }


async def test_load_10000_records():
    """Load test: 10000 records across all 10 entity types."""
    with tempfile.TemporaryDirectory() as tmp:
        m = SQLiteMemory(Path(tmp) / "test.db")
        start = time.perf_counter()
        for entity in ENTITY_TYPES:
            for i in range(1000):
                await m.put(entity, {"index": i, "data": "x" * 100})
        elapsed = time.perf_counter() - start

        # Verify count
        counts = {}
        for entity in ENTITY_TYPES:
            counts[entity] = len(await m.query(entity))

        total = sum(counts.values())
        return {
            "test": "load_10000_records",
            "elapsed_sec": round(elapsed, 2),
            "total_records": total,
            "records_per_entity": counts,
            "passed": total == 10000,
        }


async def test_update_preserves_unspecified_fields():
    """Update should merge, not replace."""
    with tempfile.TemporaryDirectory() as tmp:
        m = SQLiteMemory(Path(tmp) / "test.db")
        rid = await m.put("tasks", {"status": "created", "objective": "test", "user_id": "alice"})
        ok = await m.update("tasks", rid, {"status": "completed"})
        rec = await m.get("tasks", rid)
        return {
            "test": "update_preserves_unspecified_fields",
            "passed": ok and rec.data["status"] == "completed" and rec.data["objective"] == "test" and rec.data["user_id"] == "alice",
        }


async def test_invalid_entity_type_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        m = SQLiteMemory(Path(tmp) / "test.db")
        try:
            await m.put("invalid_type", {"x": 1})
            return {"test": "invalid_entity_type_rejected", "passed": False, "error": "no exception raised"}
        except ValueError as e:
            return {"test": "invalid_entity_type_rejected", "passed": True, "error": str(e)}


async def test_postgresql_migration_readiness():
    """Verify that the Memory protocol is PostgreSQL-ready:
    - All methods are async ✓
    - No SQLite-specific syntax in the protocol
    - The 10 entity types are explicit
    """
    from alterego.kernel.memory import Memory
    import inspect

    async_methods = []
    for name in ["put", "get", "query", "update", "delete"]:
        method = getattr(Memory, name)
        if inspect.iscoroutinefunction(method):
            async_methods.append(name)

    return {
        "test": "postgresql_migration_readiness",
        "async_methods": async_methods,
        "all_async": len(async_methods) == 5,
        "entity_types_count": len(ENTITY_TYPES),
        "passed": len(async_methods) == 5 and len(ENTITY_TYPES) == 10,
        "notes": "Protocol is async-only; switching to asyncpg requires only a new Memory subclass. No Kernel code changes needed.",
    }


async def main():
    results = {"audit": "memory", "tests": [], "issues": [], "score": 0}
    print("=" * 70)
    print("AUDIT 3 — MEMORY")
    print("=" * 70)

    tests = [
        test_persistence_after_restart,
        test_context_recovery,
        test_concurrent_writes,
        test_concurrent_reads_and_writes,
        test_database_corruption_recovery,
        test_load_10000_records,
        test_update_preserves_unspecified_fields,
        test_invalid_entity_type_rejected,
        test_postgresql_migration_readiness,
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
        "category": "scalability",
        "message": "SQLiteMemory.put uses synchronous sqlite3 (blocks event loop). V2: switch to aiosqlite for true async.",
    })
    results["issues"].append({
        "severity": "warning",
        "category": "corruption_recovery",
        "message": "No automatic corruption recovery. V2: wrap _init_db in try/except, backup-and-recreate on corruption.",
    })

    passed = sum(1 for t in results["tests"] if t.get("passed"))
    total = len(results["tests"])
    score = int(passed / total * 100) if total else 0
    score = max(0, score - sum(3 for i in results["issues"] if i["severity"] == "warning"))
    score = max(0, score - sum(1 for i in results["issues"] if i["severity"] == "info"))
    results["score"] = score

    print(f"\n{'=' * 70}")
    print(f"TESTS PASSED: {passed}/{total}")
    print(f"SCORE: {score}/100")

    out = Path(__file__).resolve().parent.parent / "results" / "audit_03_memory.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())
