"""PHASE 2.9 — SCÉNARIO 7 : Gestion mémoire.

Créer 100 conversations.
Redémarrer.
Vérifier :
- récupération
- contexte
- préférences
- missions.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from alterego.kernel.memory import SQLiteMemory, ENTITY_TYPES


async def phase1_create_data(memory: SQLiteMemory) -> dict:
    """Create 100 conversations, 5 preferences, 10 missions."""
    print("  → Création de 100 conversations...")
    conv_ids = []
    for i in range(100):
        rid = await memory.put("conversations", {
            "user_id": "alice" if i % 2 == 0 else "bob",
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i} of conversation batch",
            "timestamp": i,
            "topic": f"topic_{i % 10}",
        })
        conv_ids.append(rid)

    print("  → Création de 5 préférences...")
    pref_ids = []
    prefs = [
        {"user_id": "alice", "key": "language", "value": "fr"},
        {"user_id": "alice", "key": "theme", "value": "dark"},
        {"user_id": "alice", "key": "notifications", "value": "telegram"},
        {"user_id": "bob", "key": "language", "value": "en"},
        {"user_id": "bob", "key": "theme", "value": "light"},
    ]
    for p in prefs:
        rid = await memory.put("preferences", p)
        pref_ids.append(rid)

    print("  → Création de 10 missions...")
    mission_ids = []
    for i in range(10):
        rid = await memory.put("tasks", {
            "user_id": "alice",
            "objective": f"Mission {i}: analyse project {i}",
            "status": "completed" if i < 7 else "running",
            "result": {"summary": f"Mission {i} result"},
        })
        mission_ids.append(rid)

    return {
        "conversations_created": len(conv_ids),
        "preferences_created": len(pref_ids),
        "missions_created": len(mission_ids),
        "conv_ids": conv_ids,
        "pref_ids": pref_ids,
        "mission_ids": mission_ids,
    }


async def phase2_verify_after_restart(db_path: Path, created: dict) -> dict:
    """Simulate restart: new SQLiteMemory instance on the same DB file."""
    print("  → Redémarrage simulé (nouvelle instance SQLiteMemory)...")
    memory = SQLiteMemory(db_path)

    print("  → Vérification récupération...")
    # Conversations
    all_convs = await memory.query("conversations")
    alice_convs = await memory.query("conversations", user_id="alice")
    bob_convs = await memory.query("conversations", user_id="bob")
    topic_0_convs = await memory.query("conversations", topic="topic_0")

    # Preferences
    all_prefs = await memory.query("preferences")
    alice_prefs = await memory.query("preferences", user_id="alice")

    # Missions
    all_missions = await memory.query("tasks")
    completed_missions = await memory.query("tasks", status="completed")

    # Verify each created ID is retrievable
    print("  → Vérification ID par ID...")
    conv_recovered = 0
    for cid in created["conv_ids"]:
        rec = await memory.get("conversations", cid)
        if rec:
            conv_recovered += 1

    pref_recovered = 0
    for pid in created["pref_ids"]:
        rec = await memory.get("preferences", pid)
        if rec:
            pref_recovered += 1

    mission_recovered = 0
    for mid in created["mission_ids"]:
        rec = await memory.get("tasks", mid)
        if rec:
            mission_recovered += 1

    return {
        "conversations_total": len(all_convs),
        "conversations_alice": len(alice_convs),
        "conversations_bob": len(bob_convs),
        "conversations_topic_0": len(topic_0_convs),
        "preferences_total": len(all_prefs),
        "preferences_alice": len(alice_prefs),
        "missions_total": len(all_missions),
        "missions_completed": len(completed_missions),
        "conversations_recovered_by_id": conv_recovered,
        "preferences_recovered_by_id": pref_recovered,
        "missions_recovered_by_id": mission_recovered,
    }


async def main():
    print("=" * 70)
    print("PHASE 2.9 — SCÉNARIO 7 : GESTION MÉMOIRE")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"

        # Phase 1: create data
        print("\n── Phase 1 : Création des données ──")
        memory1 = SQLiteMemory(db_path)
        created = await phase1_create_data(memory1)
        print(f"  ✓ {created['conversations_created']} conversations")
        print(f"  ✓ {created['preferences_created']} préférences")
        print(f"  ✓ {created['missions_created']} missions")
        del memory1  # simulate process exit

        # Phase 2: restart and verify
        print("\n── Phase 2 : Redémarrage + vérification ──")
        verified = await phase2_verify_after_restart(db_path, created)

        # Validation criteria
        criteria = {
            "100_conversations_recovered": verified["conversations_total"] == 100,
            "alice_conversations_correct": verified["conversations_alice"] == 50,  # 0,2,4,...,98 = 50
            "bob_conversations_correct": verified["conversations_bob"] == 50,
            "topic_filter_works": verified["conversations_topic_0"] == 10,  # 0,10,20,...,90
            "5_preferences_recovered": verified["preferences_total"] == 5,
            "alice_preferences_correct": verified["preferences_alice"] == 3,
            "10_missions_recovered": verified["missions_total"] == 10,
            "completed_missions_correct": verified["missions_completed"] == 7,
            "all_conv_ids_recovered": verified["conversations_recovered_by_id"] == 100,
            "all_pref_ids_recovered": verified["preferences_recovered_by_id"] == 5,
            "all_mission_ids_recovered": verified["missions_recovered_by_id"] == 10,
        }

        print(f"\n── Résultats ──")
        for k, v in verified.items():
            print(f"  {k}: {v}")

        print(f"\n── Critères de validation ──")
        for k, v in criteria.items():
            print(f"  {'✓' if v else '✗'} {k}")

        passed = all(criteria.values())
        print(f"\nSCÉNARIO 7: {'✓ PASS' if passed else '✗ FAIL'}")

        out = Path(__file__).resolve().parent.parent / "results" / "scenario_07_memory.json"
        out.write_text(json.dumps({
            "scenario": 7,
            "passed": passed,
            "criteria": criteria,
            "created": {k: v for k, v in created.items() if not k.endswith("_ids")},
            "verified": verified,
        }, indent=2, default=str))
        print(f"Results saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())
