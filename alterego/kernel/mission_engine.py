"""ALTEREGO OS — Mission Engine.

Owns the lifecycle of a Mission:
  created → planned → running → validating → completed (or failed)

Coordinates Chief Of Staff, Decision Engine, Planner, Plugin Manager, EventBus.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from loguru import logger

from alterego.kernel.base import Mission, MissionStatus
from alterego.kernel.decision_engine import DecisionEngine
from alterego.kernel.event_bus import EventBus
from alterego.kernel.memory import Memory
from alterego.kernel.plugin_manager import PluginManager


class MissionEngine:
    """Drives a mission from creation to completion."""

    def __init__(
        self,
        memory: Memory,
        event_bus: EventBus,
        decision_engine: DecisionEngine,
        plugin_manager: PluginManager,
        validation_pipeline: Any = None,
    ) -> None:
        self.memory = memory
        self.event_bus = event_bus
        self.decision_engine = decision_engine
        self.plugin_manager = plugin_manager
        self.validation = validation_pipeline

    async def create(self, objective: str, user_id: str = "default") -> Mission:
        """Create a new mission and persist it."""
        mission = Mission(
            id=str(uuid.uuid4()),
            objective=objective,
            user_id=user_id,
            status=MissionStatus.CREATED,
        )
        mission_id = await self.memory.put(
            "tasks",
            {"objective": objective, "status": mission.status.value, "user_id": user_id},
            id=mission.id,
        )
        await self.event_bus.publish(
            "mission.created",
            {"mission_id": mission.id, "objective": objective},
            source="mission_engine",
        )
        logger.info(f"mission created: {mission.id} :: {objective[:80]}")
        return mission

    async def run(self, mission: Mission) -> Mission:
        """Plan + execute a mission end-to-end.

        If mission.plan is already set (e.g. by ChiefOfStaff V1.1), skip planning.
        """
        try:
            # 1. Plan (skip if already planned by ChiefOfStaff)
            if mission.plan:
                # Plan already exists — convert to Task objects for execution
                from alterego.kernel.planner import Task
                plan = [Task(**t) if isinstance(t, dict) else t for t in mission.plan]
            else:
                mission.status = MissionStatus.PLANNED
                plan = await self.decision_engine.analyze_and_plan(mission)
                mission.plan = [t.model_dump() for t in plan]
            await self.memory.update("tasks", mission.id, {"status": mission.status.value, "plan": mission.plan})

            # 2. Execute
            mission.status = MissionStatus.RUNNING
            await self.memory.update("tasks", mission.id, {"status": mission.status.value})
            await self.event_bus.publish(
                "mission.running",
                {"mission_id": mission.id, "task_count": len(plan)},
                source="mission_engine",
            )

            results = []
            for task in plan:
                result = await self._execute_task(mission, task)
                results.append({"step": task.step, "description": task.description, "result": result})

            # 3. Validate (V1: skip, just mark validating then completed)
            mission.status = MissionStatus.VALIDATING
            await self.memory.update("tasks", mission.id, {"status": mission.status.value})

            # 4. Complete
            mission.status = MissionStatus.COMPLETED
            mission.result = results
            mission.completed_at = datetime.utcnow()
            mission.touch()
            await self.memory.update(
                "tasks",
                mission.id,
                {"status": mission.status.value, "result": results, "completed_at": mission.completed_at.isoformat()},
            )
            await self.event_bus.publish(
                "mission.completed",
                {"mission_id": mission.id, "task_count": len(results)},
                source="mission_engine",
            )
            logger.info(f"mission completed: {mission.id}")
            return mission

        except Exception as e:
            mission.status = MissionStatus.FAILED
            mission.error = str(e)
            mission.touch()
            await self.memory.update(
                "tasks",
                mission.id,
                {"status": mission.status.value, "error": str(e)},
            )
            await self.event_bus.publish(
                "mission.failed",
                {"mission_id": mission.id, "error": str(e)},
                source="mission_engine",
            )
            logger.error(f"mission failed: {mission.id} :: {e}")
            return mission

    async def _execute_task(self, mission: Mission, task) -> Any:
        """Execute one task by looking up the right plugin for its capability."""
        plugin = self.plugin_manager.best_for(task.capability)
        if not plugin:
            raise RuntimeError(f"no plugin available for capability '{task.capability}'")
        logger.info(f"task {task.step}: {task.description} [{task.capability}.{task.method}]")
        await self.event_bus.publish(
            "plugin.called",
            {"mission_id": mission.id, "capability": task.capability, "method": task.method, "plugin": plugin.plugin_spec.name},
            source="mission_engine",
        )
        try:
            result = await plugin.call(task.method, task.params)

            # Validation Pipeline (V1.2) — validate LLM outputs before delivery
            if self.validation and task.capability == "llm.chat" and isinstance(result, dict):
                content = result.get("content", "")
                if content:
                    val_result = await self.validation.validate(
                        content=content,
                        context={"objective": mission.objective, "params": task.params},
                        capability=task.capability,
                        method=task.method,
                    )
                    logger.info(f"task {task.step} validation: {val_result.overall_score:.0%} deliver={val_result.can_deliver}")
                    # If validation blocked delivery, replace content with explanation
                    if not val_result.can_deliver:
                        result["content"] = f"[Validation: output blocked — {val_result.summary()}]"
                        result["validation"] = {
                            "score": val_result.overall_score,
                            "can_deliver": val_result.can_deliver,
                            "steps": [{"name": s.name, "status": s.status.value, "message": s.message} for s in val_result.steps],
                        }
                    else:
                        result["validation"] = {
                            "score": val_result.overall_score,
                            "can_deliver": True,
                        }

            return result
        except Exception as e:
            await self.event_bus.publish(
                "plugin.failed",
                {"mission_id": mission.id, "capability": task.capability, "method": task.method, "error": str(e)},
                source="mission_engine",
            )
            raise
