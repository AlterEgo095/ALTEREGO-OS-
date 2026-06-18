"""ALTEREGO OS V2 — Goal Engine.

L'utilisateur n'exprime plus des tâches. Il exprime des objectifs.
Le système décompose automatiquement :

  Goal → Objectives → Projects → Missions → Tasks → Capabilities → Plugins → Execution → Validation → Learning → Memory

Le suivi des objectifs est persistant. Chaque objectif a :
  - un status (active, paused, completed, abandoned)
  - des sous-objectifs
  - des projets associés
  - des missions générées
  - une progression mesurée
  - un historique

Exemple:
  Goal: "Faire évoluer AENEWS"
    → Objective: "Améliorer le parsing RSS"
      → Mission: "Analyser le code de parsing RSS"
    → Objective: "Ajouter support WhatsApp"
      → Mission: "Implémenter le bridge WhatsApp"
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Objective(BaseModel):
    """A sub-objective within a goal."""
    id: str
    title: str
    description: str = ""
    status: GoalStatus = GoalStatus.ACTIVE
    missions: list[str] = Field(default_factory=list)  # mission IDs
    created_at: str = ""
    completed_at: str = ""


class Goal(BaseModel):
    """A top-level user goal. Persistent, trackable, decomposable."""
    id: str
    title: str
    description: str = ""
    status: GoalStatus = GoalStatus.ACTIVE
    objectives: list[Objective] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)  # project names
    priority: int = 50  # 0-100, higher = more important
    created_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    tags: list[str] = Field(default_factory=list)

    def progress(self) -> float:
        """Return 0.0 to 1.0 — fraction of objectives completed."""
        if not self.objectives:
            return 0.0
        done = sum(1 for o in self.objectives if o.status == GoalStatus.COMPLETED)
        return done / len(self.objectives)

    def summary(self) -> str:
        lines = [
            f"Goal: {self.title} [{self.status.value}] (priority={self.priority})",
            f"  Progress: {self.progress():.0%} ({sum(1 for o in self.objectives if o.status == GoalStatus.COMPLETED)}/{len(self.objectives)} objectives)",
        ]
        for obj in self.objectives:
            icon = "✓" if obj.status == GoalStatus.COMPLETED else ("⏸" if obj.status == GoalStatus.PAUSED else "→")
            lines.append(f"  {icon} {obj.title} ({len(obj.missions)} missions)")
        if self.projects:
            lines.append(f"  Projects: {', '.join(self.projects)}")
        return "\n".join(lines)


class GoalEngine:
    """Manages persistent goals, decomposes them into objectives and missions.

    The Goal Engine sits above the Mission Engine. When a user expresses
    a goal (not a simple task), the Goal Engine:
      1. Creates a Goal record (persisted in Memory)
      2. Uses the LLM to decompose into Objectives
      3. For each Objective, suggests Missions (via Planner)
      4. Tracks progress over time
      5. Reports status on demand
    """

    DECOMPOSE_PROMPT = """You are the Goal Engine of ALTEREGO OS.
Your job is to decompose a user's goal into 2-5 concrete objectives.

A goal is a high-level aspiration. An objective is a specific, measurable
outcome that can be achieved through missions.

Output ONLY a JSON array of objectives:
[{"title":"short title","description":"one sentence"}]

Rules:
- 2 to 5 objectives maximum
- Each objective should be independently achievable
- Objectives should be ordered by priority
- Be specific and actionable
- No markdown, no explanation, ONLY the JSON array"""

    def __init__(self, memory: Any, llm_plugin: Any = None) -> None:
        self.memory = memory
        self.llm = llm_plugin

    async def create_goal(
        self,
        title: str,
        description: str = "",
        priority: int = 50,
        tags: list[str] | None = None,
        auto_decompose: bool = True,
    ) -> Goal:
        """Create a new goal and optionally decompose it into objectives."""
        goal = Goal(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            priority=priority,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            tags=tags or [],
        )

        if auto_decompose and self.llm:
            objectives = await self._decompose(title, description)
            goal.objectives = objectives

        # Persist
        await self.memory.put("knowledge", {
            "type": "goal",
            **goal.model_dump(),
        })
        logger.info(f"GoalEngine: created goal '{title}' with {len(goal.objectives)} objectives")
        return goal

    async def _decompose(self, title: str, description: str) -> list[Objective]:
        """Use LLM to decompose a goal into objectives."""
        try:
            result = await self.llm.call("chat", {
                "system": self.DECOMPOSE_PROMPT,
                "user": f"Goal: {title}\nDescription: {description}",
                "temperature": 0.3,
            })
            import json
            content = result.get("content", "") if isinstance(result, dict) else str(result)

            # Parse JSON array
            # Strip markdown fences if present
            import re
            content = content.strip()
            fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
            if fence:
                content = fence.group(1).strip()

            # Find JSON array
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                items = json.loads(content[start:end])
                objectives = []
                for item in items:
                    objectives.append(Objective(
                        id=str(uuid.uuid4()),
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        created_at=datetime.utcnow().isoformat(),
                    ))
                return objectives
        except Exception as e:
            logger.warning(f"GoalEngine: decomposition failed: {e}")

        # Fallback: single objective
        return [Objective(
            id=str(uuid.uuid4()),
            title=title,
            description=description or "Auto-generated objective",
            created_at=datetime.utcnow().isoformat(),
        )]

    async def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Retrieve a goal by ID.

        The goal_id is stored INSIDE the data (goal.id field), not as the
        memory record ID. We need to query all knowledge records and filter.
        """
        records = await self.memory.query("knowledge")
        for r in records:
            if r.data.get("type") != "goal":
                continue
            if r.data.get("id") == goal_id:
                data = r.data.copy()
                data.pop("type", None)
                try:
                    return Goal(**data)
                except Exception as e:
                    logger.error(f"GoalEngine: failed to parse goal {goal_id}: {e}")
                    return None
        return None

    async def list_goals(self, status: GoalStatus | None = None) -> list[Goal]:
        """List all goals, optionally filtered by status."""
        records = await self.memory.query("knowledge")
        goals = []
        for r in records:
            if r.data.get("type") != "goal":
                continue
            data = r.data.copy()
            data.pop("type", None)
            try:
                goal = Goal(**data)
                if status is None or goal.status == status:
                    goals.append(goal)
            except Exception:
                pass
        goals.sort(key=lambda g: g.priority, reverse=True)
        return goals

    async def update_goal(self, goal_id: str, **updates: Any) -> bool:
        """Update a goal's fields."""
        goal = await self.get_goal(goal_id)
        if not goal:
            return False
        for k, v in updates.items():
            if hasattr(goal, k):
                setattr(goal, k, v)
        goal.updated_at = datetime.utcnow().isoformat()
        # Find the memory record ID for this goal
        records = await self.memory.query("knowledge")
        record_id = None
        for r in records:
            if r.data.get("type") == "goal" and r.data.get("id") == goal_id:
                record_id = r.id
                break
        if not record_id:
            return False
        # Persist with type field preserved
        data = goal.model_dump()
        data["type"] = "goal"
        await self.memory.update("knowledge", record_id, data)
        return True

    async def complete_objective(self, goal_id: str, objective_id: str) -> bool:
        """Mark an objective as completed."""
        goal = await self.get_goal(goal_id)
        if not goal:
            return False
        for obj in goal.objectives:
            if obj.id == objective_id:
                obj.status = GoalStatus.COMPLETED
                obj.completed_at = datetime.utcnow().isoformat()
                # Check if all objectives are done
                if all(o.status == GoalStatus.COMPLETED for o in goal.objectives):
                    goal.status = GoalStatus.COMPLETED
                    goal.completed_at = datetime.utcnow().isoformat()
                await self.update_goal(goal_id, objectives=[o.model_dump() for o in goal.objectives], status=goal.status)
                logger.info(f"GoalEngine: objective '{obj.title}' completed in goal '{goal.title}'")
                return True
        return False

    async def add_mission_to_objective(self, goal_id: str, objective_id: str, mission_id: str) -> bool:
        """Link a mission to an objective."""
        goal = await self.get_goal(goal_id)
        if not goal:
            return False
        for obj in goal.objectives:
            if obj.id == objective_id:
                if mission_id not in obj.missions:
                    obj.missions.append(mission_id)
                    await self.update_goal(goal_id, objectives=[o.model_dump() for o in goal.objectives])
                    return True
        return False

    async def summary(self) -> str:
        """Human-readable summary of all goals."""
        goals = await self.list_goals()
        if not goals:
            return "No goals registered yet."
        lines = [f"Goals ({len(goals)}):"]
        for g in goals:
            lines.append(f"  {g.summary()}")
        return "\n".join(lines)
