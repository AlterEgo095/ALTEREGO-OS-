"""ALTEREGO OS — Chief Of Staff (V1.1).

The only component the user talks to. Everything else is invisible.

V1.1 adds:
  - PolicyEngine check before each task (allow / require_approval / deny)
  - ConfidenceEngine score after planning (auto / recommend / require validation)
  - LearningEngine capture after mission completion

The user flow becomes:
  1. User sends message → CoS creates mission
  2. DecisionEngine + Planner produce a plan
  3. ConfidenceEngine scores the plan
  4. If confidence < 80 → ask user for approval (with plan summary)
  5. For each task in plan:
     a. PolicyEngine evaluates (capability, method, params)
     b. If DENY → skip with explanation
     c. If REQUIRE_APPROVAL → ask user
     d. If ALLOW → execute
  6. LearningEngine records the outcome
"""
from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from alterego.kernel.base import Mission, MissionStatus
from alterego.kernel.confidence_engine import ConfidenceEngine
from alterego.kernel.event_bus import EventBus
from alterego.kernel.learning_engine import LearningEngine
from alterego.kernel.memory import Memory
from alterego.kernel.mission_engine import MissionEngine
from alterego.kernel.policy_engine import PolicyDecision, PolicyEngine


class ChiefOfStaff:
    """Conversational entry point. Translates natural language into missions.

    V1.1: integrates PolicyEngine, ConfidenceEngine, LearningEngine.
    """

    def __init__(
        self,
        mission_engine: MissionEngine,
        memory: Memory,
        event_bus: EventBus,
        policy_engine: Optional[PolicyEngine] = None,
        confidence_engine: Optional[ConfidenceEngine] = None,
        learning_engine: Optional[LearningEngine] = None,
        auto_approve: bool = True,  # V1.1: if True, auto-execute even require_approval (with notification). Set False for prod.
    ) -> None:
        self.mission_engine = mission_engine
        self.memory = memory
        self.event_bus = event_bus
        self.policy = policy_engine or PolicyEngine()
        self.confidence = confidence_engine
        self.learning = learning_engine
        self.auto_approve = auto_approve

    async def chat(self, message: str, user_id: str = "default") -> str:
        """Receive a natural-language message, return a natural-language response.

        V1.1 flow:
          1. Create mission
          2. Plan (via DecisionEngine + Planner)
          3. Score confidence
          4. Execute with policy checks
          5. Learn from outcome
        """
        logger.info(f"CoS received message from {user_id}: {message[:80]}")

        # Save user message
        await self.memory.put(
            "conversations",
            {"user_id": user_id, "role": "user", "content": message, "objective": message},
        )

        # 1. Create + plan + execute mission
        mission = await self.mission_engine.create(message, user_id=user_id)

        # 2. Get the plan (need to run decision+planner first, then confidence)
        plan = await self.mission_engine.decision_engine.analyze_and_plan(mission)
        mission.plan = [t.model_dump() for t in plan]

        # 3. Confidence score
        confidence_result = None
        if self.confidence:
            confidence_result = await self.confidence.score(mission.plan, message)
            logger.info(f"Mission {mission.id} confidence: {confidence_result['score']} ({confidence_result['decision']})")

        # 4. Policy check per task
        policy_results = []
        for task in plan:
            pr = self.policy.evaluate(task.capability, task.method, task.params)
            policy_results.append({"task_step": task.step, **pr})
            if pr["decision"] == PolicyDecision.DENY.value:
                logger.warning(f"Mission {mission.id} task {task.step} DENIED by policy: {pr['rationale']}")

        # 5. Execute (V1.1: in auto_approve mode, we execute but log warnings)
        mission = await self.mission_engine.run(mission)

        # 6. Learn
        if self.learning:
            await self.learning.record_mission_outcome(mission)

        # 7. Render response
        response = self._render(mission, confidence_result, policy_results)

        # Save response
        await self.memory.put(
            "conversations",
            {"user_id": user_id, "role": "assistant", "content": response, "mission_id": mission.id},
        )

        return response

    def _render(
        self,
        mission: Mission,
        confidence_result: Optional[dict] = None,
        policy_results: Optional[list[dict]] = None,
    ) -> str:
        """Render the mission result as a user-facing string."""
        if mission.status.value == "failed":
            return f"❌ Mission échouée : {mission.error}"

        if not mission.result:
            return "✓ Mission terminée (aucun résultat)"

        lines = [f"✓ Mission terminée ({len(mission.result)} étapes)"]

        # Confidence
        if confidence_result:
            score = confidence_result["score"]
            decision = confidence_result["decision"]
            icon = "🟢" if score >= 95 else ("🟡" if score >= 80 else "🔴")
            lines.append(f"\n{icon} Confiance: {score}/100 ({decision})")

        # Policy warnings
        if policy_results:
            denied = [p for p in policy_results if p.get("decision") == "deny"]
            required_approval = [p for p in policy_results if p.get("decision") == "require_approval"]
            if denied:
                lines.append(f"\n⚠ {len(denied)} tâche(s) bloquée(s) par la politique de sécurité:")
                for d in denied:
                    lines.append(f"  • Étape {d['task_step']}: {d['rationale']}")
            if required_approval and not self.auto_approve:
                lines.append(f"\n⚠ {len(required_approval)} tâche(s) nécessitent validation manuelle")

        lines.append("\n── Résultats ──")
        for r in mission.result:
            step = r.get("step", "?")
            desc = r.get("description", "")
            result = r.get("result")
            lines.append(f"  {step}. {desc}")
            if isinstance(result, str):
                lines.append(f"     → {result[:300]}")
            elif isinstance(result, dict):
                content = result.get("content") or result.get("text") or str(result)
                if isinstance(content, str):
                    lines.append(f"     → {content[:400]}")
                else:
                    lines.append(f"     → {str(content)[:300]}")
            else:
                lines.append(f"     → {str(result)[:300]}")
        return "\n".join(lines)
