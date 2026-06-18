"""ALTEREGO OS — Learning Engine.

After each mission, captures feedback and updates memory so the system
improves over time.

Learning loop:
  Mission → Result → Feedback → Memory → Improvement

V1.1 captures:
  - mission success/failure per capability (feeds ConfidenceEngine)
  - user feedback (thumbs up/down + free text)
  - common failure patterns (for future auto-repair)
  - user preferences inferred from behavior
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from alterego.kernel.base import Mission, MissionStatus


class LearningEngine:
    """Captures post-mission feedback and updates memory.

    The LearningEngine is invoked by the ChiefOfStaff after each mission.
    It does NOT modify the Kernel or plugins — it only updates memory
    so that future missions benefit from past experience.
    """

    def __init__(self, memory: Any, event_bus: Any) -> None:
        self.memory = memory
        self.bus = event_bus

    async def record_mission_outcome(self, mission: Mission) -> None:
        """Record the outcome of a mission in memory for future learning.

        Stores in 'tasks' entity (already done by MissionEngine) and
        additionally stores a learning record in 'knowledge' entity.
        """
        if not mission.plan:
            return

        # Extract per-capability outcomes
        cap_outcomes: dict[str, dict[str, int]] = {}
        for task_dict in mission.plan:
            cap = task_dict.get("capability", "unknown")
            if cap not in cap_outcomes:
                cap_outcomes[cap] = {"success": 0, "failure": 0}
            if mission.status == MissionStatus.COMPLETED:
                cap_outcomes[cap]["success"] += 1
            elif mission.status == MissionStatus.FAILED:
                cap_outcomes[cap]["failure"] += 1

        # Store learning record
        learning_record = {
            "mission_id": mission.id,
            "objective": mission.objective[:200],
            "status": mission.status.value,
            "capability_outcomes": cap_outcomes,
            "task_count": len(mission.plan),
            "error": mission.error,
            "learned_at": datetime.utcnow().isoformat(),
        }
        await self.memory.put("knowledge", learning_record)
        logger.debug(f"LearningEngine: recorded outcome for mission {mission.id}")

    async def record_user_feedback(self, mission_id: str, feedback: str, rating: int) -> None:
        """Record explicit user feedback for a mission.

        Args:
            mission_id: The mission ID
            feedback: Free-text feedback from user
            rating: -1 (negative), 0 (neutral), 1 (positive)
        """
        await self.memory.put("knowledge", {
            "type": "user_feedback",
            "mission_id": mission_id,
            "feedback": feedback,
            "rating": rating,
            "recorded_at": datetime.utcnow().isoformat(),
        })
        logger.info(f"LearningEngine: recorded user feedback for mission {mission_id} (rating={rating})")

    async def get_capability_stats(self) -> dict[str, dict[str, int]]:
        """Get aggregated success/failure stats per capability."""
        records = await self.memory.query("knowledge")
        stats: dict[str, dict[str, int]] = {}
        for r in records:
            if "capability_outcomes" not in r.data:
                continue
            for cap, outcome in r.data["capability_outcomes"].items():
                if cap not in stats:
                    stats[cap] = {"success": 0, "failure": 0}
                stats[cap]["success"] += outcome.get("success", 0)
                stats[cap]["failure"] += outcome.get("failure", 0)
        return stats

    async def infer_preference(self, user_id: str, key: str, value: Any) -> None:
        """Infer a user preference from behavior and store it.

        Examples:
          - User always asks for French responses → preference: language=fr
          - User always approves SSH missions during work hours → preference: auto_approve_ssh_workhours=True
        """
        existing = await self.memory.query("preferences", user_id=user_id, key=key)
        if existing:
            # Update existing
            await self.memory.update("preferences", existing[0].id, {"value": value, "inferred": True})
        else:
            await self.memory.put("preferences", {
                "user_id": user_id,
                "key": key,
                "value": value,
                "inferred": True,
                "inferred_at": datetime.utcnow().isoformat(),
            })
        logger.debug(f"LearningEngine: inferred preference {key}={value} for user {user_id}")
