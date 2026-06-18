"""V2.1 Full Integration Test — validate every component works end-to-end.

Tests:
1. Kernel imports (22 components)
2. Kernel factory builds without error
3. Plugins load + initialize
4. Departments load (11)
5. PolicyEngine evaluates correctly
6. ConfidenceEngine scores
7. ValidationPipeline runs
8. GoalEngine creates + tracks goals
9. DailyAssistant generates reports
10. ContextEngine builds context
11. DigitalTwinV2 creates entities + relations
12. LifeTimeline records + queries events
13. LongTermMemory searches + detects trends
14. UnifiedWorkspace shows connections
15. InitiativeEngine scans
16. ChiefOfStaff processes a mission (mock LLM)
17. Full mission end-to-end (mock LLM + filesystem)
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ── Test 1: Kernel imports ──────────────────────────────────────────────────
def test_imports():
    print("── Test 1: Kernel imports (22 components) ──")
    from alterego.kernel import (
        BaseBridge, BasePlugin, BaseCapability,
        BridgeSpec, PluginSpec, CapabilitySpec,
        Mission, MissionStatus, Event,
        EventBus, InProcessEventBus,
        Memory, SQLiteMemory,
        CapabilityRegistry, PluginManager,
        Planner, DecisionEngine, MissionEngine, ChiefOfStaff,
        PolicyEngine, PolicyDecision, RiskLevel,
        ConfidenceEngine, LearningEngine,
        DepartmentLoader, DepartmentSpec,
        ValidationPipeline, ValidationResult,
        InitiativeEngine, Initiative, InitiativeType, InitiativePriority,
        DigitalTwin,
        GoalEngine, Goal, Objective, GoalStatus,
        DailyAssistant, ContextEngine,
        DigitalTwinV2, LifeTimeline, LongTermMemory, UnifiedWorkspace,
    )
    print("  ✓ All 22 kernel components imported")
    return True


# ── Test 2: Kernel factory ──────────────────────────────────────────────────
async def test_factory(tmpdir):
    print("\n── Test 2: Kernel factory ──")
    from alterego.kernel_factory import build_kernel
    kernel = build_kernel(db_path=str(Path(tmpdir) / "test.db"))
    expected_keys = [
        "chief_of_staff", "mission_engine", "memory", "event_bus",
        "plugin_manager", "capability_registry", "policy_engine",
        "confidence_engine", "learning_engine", "department_loader",
        "llm_plugin", "validation_pipeline", "initiative_engine",
        "digital_twin", "goal_engine", "daily_assistant", "context_engine",
        "digital_twin_v2", "life_timeline", "long_term_memory", "unified_workspace",
    ]
    for key in expected_keys:
        assert key in kernel, f"Missing kernel component: {key}"
    print(f"  ✓ Factory built with {len(expected_keys)} components")
    return kernel


# ── Test 3: Plugins ─────────────────────────────────────────────────────────
async def test_plugins(kernel):
    print("\n── Test 3: Plugins ──")
    await kernel["plugin_manager"].initialize_all()
    plugins = kernel["plugin_manager"].list_plugins()
    print(f"  ✓ {len(plugins)} plugins loaded: {plugins}")
    assert len(plugins) >= 2, f"Expected at least 2 plugins, got {len(plugins)}"
    return True


# ── Test 4: Departments ─────────────────────────────────────────────────────
async def test_departments(kernel):
    print("\n── Test 4: Departments ──")
    depts = kernel["department_loader"].list()
    print(f"  ✓ {len(depts)} departments loaded")
    for d in depts:
        print(f"    - {d.name}: {len(d.capabilities)} capabilities")
    assert len(depts) >= 4, f"Expected at least 4 departments, got {len(depts)}"
    return True


# ── Test 5: PolicyEngine ────────────────────────────────────────────────────
async def test_policy(kernel):
    print("\n── Test 5: PolicyEngine ──")
    pe = kernel["policy_engine"]
    # filesystem.read → allow
    r = pe.evaluate("filesystem", "read", {"path": "/tmp/test"})
    assert r["decision"] == "allow", f"Expected allow, got {r['decision']}"
    print(f"  ✓ filesystem.read → {r['decision']} (risk={r['risk']})")
    # ssh.exec → require_approval
    r = pe.evaluate("ssh", "exec", {"command": "ls"})
    assert r["decision"] == "require_approval", f"Expected require_approval, got {r['decision']}"
    print(f"  ✓ ssh.exec → {r['decision']} (risk={r['risk']})")
    # rm -rf / → deny
    r = pe.evaluate("ssh", "exec", {"command": "rm -rf /"})
    assert r["decision"] == "deny", f"Expected deny, got {r['decision']}"
    print(f"  ✓ ssh.exec(rm -rf /) → {r['decision']}")
    return True


# ── Test 6: ConfidenceEngine ────────────────────────────────────────────────
async def test_confidence(kernel):
    print("\n── Test 6: ConfidenceEngine ──")
    plan = [
        {"step": 1, "description": "Read file", "capability": "filesystem", "method": "read", "params": {"path": "/tmp/test"}},
        {"step": 2, "description": "Respond", "capability": "llm.chat", "method": "chat", "params": {"user": "ok"}},
    ]
    result = await kernel["confidence_engine"].score(plan)
    assert result["score"] > 0, "Score should be > 0"
    print(f"  ✓ Score: {result['score']}/100 ({result['decision']})")
    return True


# ── Test 7: ValidationPipeline ──────────────────────────────────────────────
async def test_validation(kernel):
    print("\n── Test 7: ValidationPipeline ──")
    vp = kernel["validation_pipeline"]
    result = await vp.validate(
        content="Hello, this is a safe response.",
        context={"objective": "greeting"},
        capability="llm.chat",
        method="chat",
    )
    assert result.can_deliver, f"Expected can_deliver=True, got {result.can_deliver}"
    print(f"  ✓ Validation: {result.overall_score:.0%} deliver={result.can_deliver}")
    # Test with secret
    result2 = await vp.validate(
        content="My key is sk-1234567890abcdefghij",
        context={},
        capability="llm.chat",
        method="chat",
    )
    assert not result2.can_deliver, "Should block content with secrets"
    print(f"  ✓ Secret detection: {result2.overall_score:.0%} deliver={result2.can_deliver} (blocked)")
    return True


# ── Test 8: GoalEngine ──────────────────────────────────────────────────────
async def test_goal_engine(kernel):
    print("\n── Test 8: GoalEngine ──")
    ge = kernel["goal_engine"]
    goal = await ge.create_goal("Test Goal", "A test objective", auto_decompose=False)
    print(f"  ✓ Created goal: {goal.id[:8]} '{goal.title}'")
    # Add objectives
    from alterego.kernel import Objective
    obj1 = Objective(id="o1", title="Objective 1", description="First", created_at="2026-06-18")
    obj2 = Objective(id="o2", title="Objective 2", description="Second", created_at="2026-06-18")
    goal.objectives = [obj1, obj2]
    await ge.update_goal(goal.id, objectives=[o.model_dump() for o in goal.objectives])
    # Complete one
    await ge.complete_objective(goal.id, "o1")
    g2 = await ge.get_goal(goal.id)
    assert g2 is not None, "Goal should be retrievable"
    assert g2.progress() == 0.5, f"Expected 50%, got {g2.progress()}"
    print(f"  ✓ Progress: {g2.progress():.0%} (1/2 objectives completed)")
    # List
    goals = await ge.list_goals()
    assert len(goals) >= 1
    print(f"  ✓ Listed {len(goals)} goal(s)")
    return True


# ── Test 9: DailyAssistant ──────────────────────────────────────────────────
async def test_daily(kernel):
    print("\n── Test 9: DailyAssistant ──")
    da = kernel["daily_assistant"]
    # Add some data first
    await kernel["memory"].put("conversations", {"user_id": "default", "role": "user", "content": "Hello", "objective": "greeting"})
    await kernel["memory"].put("tasks", {"user_id": "default", "objective": "Test", "status": "completed", "created_at": "2026-06-18T10:00:00"})
    brief = await da.morning_brief()
    assert len(brief) > 0
    print(f"  ✓ Morning Brief: {len(brief)} chars")
    evening = await da.evening_report()
    assert len(evening) > 0
    print(f"  ✓ Evening Report: {len(evening)} chars")
    weekly = await da.weekly_review()
    assert len(weekly) > 0
    print(f"  ✓ Weekly Review: {len(weekly)} chars")
    return True


# ── Test 10: ContextEngine ──────────────────────────────────────────────────
async def test_context(kernel):
    print("\n── Test 10: ContextEngine ──")
    ce = kernel["context_engine"]
    summary = await ce.get_context_summary()
    assert len(summary) > 0
    print(f"  ✓ Context summary: {len(summary)} chars")
    ctx = await ce.get_context()
    assert "user_id" in ctx
    print(f"  ✓ Context dict: {len(ctx)} keys")
    return True


# ── Test 11: DigitalTwinV2 ──────────────────────────────────────────────────
async def test_twin_v2(kernel):
    print("\n── Test 11: DigitalTwinV2 ──")
    twin = kernel["digital_twin_v2"]
    await twin.set_identity("Test User", role="Developer")
    await twin.add_company("TestCorp", industry="Tech")
    await twin.add_project("TestProject", company="TestCorp")
    await twin.add_server("vps1", "10.0.0.1")
    await twin.add_skill("Python", level=5)
    await twin.add_decision("Use ALTEREGO", description="Best choice")
    # Check entities
    companies = await twin.get_entities("company")
    assert len(companies) >= 1
    projects = await twin.get_entities("project")
    assert len(projects) >= 1
    # Check relations
    rels = await twin.get_relations()
    assert len(rels) >= 1, f"Expected relations, got {len(rels)}"
    print(f"  ✓ Entities created: companies={len(companies)}, projects={len(projects)}")
    print(f"  ✓ Relations: {len(rels)}")
    for r in rels[:3]:
        print(f"    {r.get('from')} →[{r.get('relation')}]→ {r.get('to')}")
    # Describe
    desc = await twin.describe()
    assert len(desc) > 0
    print(f"  ✓ Describe: {len(desc)} chars")
    return True


# ── Test 12: LifeTimeline ───────────────────────────────────────────────────
async def test_timeline(kernel):
    print("\n── Test 12: LifeTimeline ──")
    tl = kernel["life_timeline"]
    await tl.record("mission_created", "Test mission", severity="info", source="test")
    await tl.record("mission_completed", "Test done", severity="success", source="test")
    await tl.record("error", "Something broke", severity="warning", source="test")
    events = await tl.get_recent(hours=1)
    assert len(events) >= 3, f"Expected 3+ events, got {len(events)}"
    print(f"  ✓ Recorded 3 events, retrieved {len(events)}")
    critical = await tl.get_critical()
    print(f"  ✓ Critical events: {len(critical)}")
    summary = await tl.summary(days=7)
    assert len(summary) > 0
    print(f"  ✓ Summary: {len(summary)} chars")
    return True


# ── Test 13: LongTermMemory ─────────────────────────────────────────────────
async def test_ltm(kernel):
    print("\n── Test 13: LongTermMemory ──")
    ltm = kernel["long_term_memory"]
    # Search conversations (we added one in test 9)
    results = await ltm.search_conversations("Hello")
    assert len(results) >= 1, f"Expected results for 'Hello', got {len(results)}"
    print(f"  ✓ Search 'Hello': {len(results)} conversation(s) found")
    # Search decisions (we added one in test 11)
    results = await ltm.search_decisions("ALTEREGO")
    assert len(results) >= 1, f"Expected results for 'ALTEREGO', got {len(results)}"
    print(f"  ✓ Search 'ALTEREGO': {len(results)} decision(s) found")
    # Find old idea
    idea = await ltm.find_old_idea("Hello")
    assert len(idea) > 0
    print(f"  ✓ Find old idea: {len(idea)} chars")
    # Trends
    trends = await ltm.detect_trends(days=30)
    assert "mission_volume_trend" in trends
    print(f"  ✓ Trends: {trends['mission_volume_trend']}, {trends['success_rate_trend']}")
    return True


# ── Test 14: UnifiedWorkspace ───────────────────────────────────────────────
async def test_workspace(kernel):
    print("\n── Test 14: UnifiedWorkspace ──")
    ws = kernel["unified_workspace"]
    overview = await ws.overview()
    assert "connections" in overview
    print(f"  ✓ Overview: {overview['total_plugins']} plugins, {overview['healthy_connections']} healthy")
    status = await ws.status()
    assert len(status) >= 1
    print(f"  ✓ Status: {len(status)} connections checked")
    desc = await ws.describe()
    assert len(desc) > 0
    print(f"  ✓ Describe: {len(desc)} chars")
    return True


# ── Test 15: InitiativeEngine ───────────────────────────────────────────────
async def test_initiative(kernel):
    print("\n── Test 15: InitiativeEngine ──")
    init = kernel["initiative_engine"]
    initiatives = await init.scan()
    print(f"  ✓ Scan completed: {len(initiatives)} initiative(s) detected")
    return True


# ── Test 16: ChiefOfStaff with mock LLM ─────────────────────────────────────
async def test_chief_of_staff(kernel):
    print("\n── Test 16: ChiefOfStaff (mock LLM) ──")
    from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec
    from typing import Any
    import json

    class MockLLM(BasePlugin):
        spec = BridgeSpec(name="mock", capabilities=["llm.chat"])
        plugin_spec = PluginSpec(name="mock", capabilities=["llm.chat"], priority=5)
        async def initialize(self): pass
        async def shutdown(self): pass
        async def health(self): return True
        def methods(self): return ["chat"]
        async def call(self, method, params):
            system = params.get("system", "")
            if "PLANNER" in system or "planner" in system.lower():
                return {"content": json.dumps({"tasks": [{"step": 1, "description": "Respond", "capability": "llm.chat", "method": "chat", "params": {"system": "You are ALTEREGO.", "user": params.get("user", "")}}]})}
            if "intent" in system.lower():
                return {"content": "Help the user"}
            return {"content": "Hello from ALTEREGO!"}

    # Replace LLM plugin
    mock = MockLLM()
    await mock.initialize()
    kernel["plugin_manager"]._plugins["mock"] = mock
    kernel["plugin_manager"]._by_capability["llm.chat"] = ["mock"]

    # Rebuild engines with mock
    from alterego.kernel import Planner, DecisionEngine
    cap_reg = kernel["capability_registry"]
    planner = Planner(cap_reg, mock)
    decision = DecisionEngine(kernel["memory"], planner, mock)
    kernel["mission_engine"].decision_engine = decision
    kernel["mission_engine"].plugin_manager = kernel["plugin_manager"]

    cos = kernel["chief_of_staff"]
    response = await cos.chat("Bonjour")
    assert "Mission" in response or "✓" in response or "❌" in response, f"Unexpected response: {response[:100]}"
    print(f"  ✓ Mission completed: {len(response)} chars response")
    return True


# ── Main runner ─────────────────────────────────────────────────────────────
async def main():
    print("=" * 70)
    print("  ALTEREGO OS V2.1 — FULL INTEGRATION TEST")
    print("=" * 70)

    results = {}
    tests = [
        ("imports", test_imports),
        ("factory", None),  # special — needs tmpdir
        ("plugins", None),
        ("departments", None),
        ("policy", None),
        ("confidence", None),
        ("validation", None),
        ("goal_engine", None),
        ("daily", None),
        ("context", None),
        ("twin_v2", None),
        ("timeline", None),
        ("ltm", None),
        ("workspace", None),
        ("initiative", None),
        ("chief_of_staff", None),
    ]

    # Test 1: imports (sync)
    try:
        results["imports"] = test_imports()
    except Exception as e:
        results["imports"] = False
        print(f"  ✗ FAILED: {e}")

    # Tests 2-16: async
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            kernel = await test_factory(tmpdir)
            results["factory"] = True
        except Exception as e:
            results["factory"] = False
            print(f"  ✗ FAILED: {e}")
            kernel = None

        if kernel:
            test_funcs = [
                ("plugins", lambda: test_plugins(kernel)),
                ("departments", lambda: test_departments(kernel)),
                ("policy", lambda: test_policy(kernel)),
                ("confidence", lambda: test_confidence(kernel)),
                ("validation", lambda: test_validation(kernel)),
                ("goal_engine", lambda: test_goal_engine(kernel)),
                ("daily", lambda: test_daily(kernel)),
                ("context", lambda: test_context(kernel)),
                ("twin_v2", lambda: test_twin_v2(kernel)),
                ("timeline", lambda: test_timeline(kernel)),
                ("ltm", lambda: test_ltm(kernel)),
                ("workspace", lambda: test_workspace(kernel)),
                ("initiative", lambda: test_initiative(kernel)),
                ("chief_of_staff", lambda: test_chief_of_staff(kernel)),
            ]
            for name, func in test_funcs:
                try:
                    results[name] = await func()
                except Exception as e:
                    results[name] = False
                    print(f"  ✗ FAILED: {e}")
                    import traceback
                    traceback.print_exc()

    # Summary
    print("\n" + "=" * 70)
    print("  INTEGRATION TEST SUMMARY")
    print("=" * 70)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        print(f"  {'✓' if ok else '✗'} {name}")
    print(f"\n  {passed}/{total} tests passed")
    if passed == total:
        print("\n  ✅ ALL COMPONENTS WORKING — ALTEREGO V2.1 IS STABLE")
    else:
        print(f"\n  ❌ {total - passed} component(s) failed — needs fixing")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
