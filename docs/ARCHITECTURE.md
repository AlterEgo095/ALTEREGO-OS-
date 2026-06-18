# ALTEREGO OS — Architecture (V1)

## 8 Kernel components

| Component           | File                       | Responsibility                                        |
|---------------------|----------------------------|-------------------------------------------------------|
| Chief Of Staff      | `chief_of_staff.py`        | Sole entry point, conversational                      |
| Mission Engine      | `mission_engine.py`        | Mission lifecycle: created → running → completed      |
| Decision Engine     | `decision_engine.py`       | Intent extraction, context retrieval, plan delegation |
| Planner             | `planner.py`               | Decomposes mission into tasks via LLM                 |
| Memory              | `memory.py`                | Centralized, 10 entity types (V1: SQLite)             |
| Event Bus           | `event_bus.py`             | In-process pub/sub (V1: asyncio; V2: NATS)            |
| Capability Registry | `capability_registry.py`   | Catalogs capabilities, NOT plugins                    |
| Plugin Manager      | `plugin_manager.py`        | Loads plugins, picks best for a capability            |

## Key principle: Capability vs Plugin

The Kernel NEVER asks for a plugin by name. It asks for a capability:

```python
# WRONG (Kernel never does this):
plugin = plugin_manager.get("github")

# RIGHT (Kernel always does this):
plugin = plugin_manager.best_for("github")  # the CAPABILITY, not the plugin
```

This lets us swap `PyGithub` → `github3.py` without touching the Decision Engine.

## Memory schema

V1 uses SQLite with a single `memory` table:

```
memory(id TEXT PK, entity_type TEXT, data TEXT (JSON), created_at TEXT, updated_at TEXT)
CREATE INDEX idx_entity ON memory(entity_type)
```

The 10 entity types (enforced):
- `projects`, `repositories`, `servers`, `containers`
- `users`, `conversations`, `tasks`
- `documents`, `preferences`, `knowledge`

V2 will switch to PostgreSQL without changing the `Memory` interface.

## Event Bus protocol

```python
# Publish
await bus.publish("mission.created", {"mission_id": "abc"}, source="mission_engine")

# Subscribe (supports * wildcards per segment)
bus.subscribe("mission.*", handler)
bus.subscribe("*", handler)  # match everything

# Unsubscribe
bus.unsubscribe(sub_id)
```

V2 will swap to NATS JetStream without changing the protocol.

## Validation pipeline (V1 partial)

V1 implements 4 of the 8 validation steps:
- ✓ LLM
- ✓ Critic (lightweight — same LLM with critic prompt)
- ✓ Validator (Pydantic schema check)
- ✓ Security (basic check for secrets/PII in output)

V2 will add: Tests, Repair loop, Final Validation, Delivery gate.

## Why no Builder in V1?

The Builder is a long-term vision. Building it prematurely leads to:
- Over-engineering for use cases that don't exist yet
- Hardcoded assumptions about what "manual" looks like
- Wasted effort automating the wrong things

Instead, V1 is built **manually**. After 5-10 manual plugin integrations, the
repetitive patterns will become obvious. The Builder will then be extracted from
those patterns — it will automate what is *actually* repetitive, not what we
*guess* is repetitive.

> **The Builder is a consequence of experience, not a starting point.**
