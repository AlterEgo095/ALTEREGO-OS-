"""ALTEREGO OS — Decision Engine.

The Decision Engine sits between the Mission Engine and the Planner. It:
  1. Analyzes the mission objective (extract intent, context).
  2. Pulls relevant context from Memory (conversations, projects, ...).
  3. Forwards to the Planner with the enriched context.

V1 keeps it simple: a single LLM call to extract intent, then delegate to Planner.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from alterego.kernel.base import Mission
from alterego.kernel.memory import Memory
from alterego.kernel.planner import Planner, Task


class DecisionEngine:
    """Analyzes a mission and produces an execution plan (via Planner)."""

    INTENT_PROMPT = """You are the Decision Engine of ALTEREGO OS.
Given a user objective, extract the user's intent in one short sentence.

Examples:
- Objective: "Analyse ce dépôt et corrige les erreurs"
  Intent: "Inspect a GitHub repository, identify code errors, and propose fixes."

- Objective: "Vérifie mon VPS"
  Intent: "Connect to a remote server via SSH and report its health status."

Output ONLY the intent (one sentence, no preamble, no quotes)."""

    def __init__(self, memory: Memory, planner: Planner, llm_plugin: Any) -> None:
        self.memory = memory
        self.planner = planner
        self.llm_plugin = llm_plugin

    async def analyze_and_plan(self, mission: Mission) -> list[Task]:
        """Analyze the mission, enrich context, then produce a plan."""
        # 1. Extract intent (helps the Planner produce a better plan)
        try:
            intent = await self.llm_plugin.call("chat", {
                "system": self.INTENT_PROMPT,
                "user": mission.objective,
                "temperature": 0.0,
            })
            if isinstance(intent, dict):
                intent = intent.get("content", str(intent))
            logger.info(f"mission {mission.id} intent: {intent}")
        except Exception as e:
            logger.warning(f"intent extraction failed ({e}); using raw objective")
            intent = mission.objective

        # 2. Pull recent conversations from memory (V1: simple context)
        recent = await self.memory.query("conversations", user_id=mission.user_id)
        context_lines = [f"- {r.data.get('summary', r.data.get('objective', '?'))}" for r in recent[-3:]]
        context = "\n".join(context_lines) if context_lines else "(no prior context)"

        # 3. Enrich the mission objective with intent + context, then plan
        enriched = f"Intent: {intent}\n\nPrior context:\n{context}\n\nOriginal objective: {mission.objective}"
        mission.objective = enriched
        mission.touch()

        # 4. Plan
        plan = await self.planner.plan(mission)
        logger.info(f"mission {mission.id} plan: {len(plan)} tasks")
        return plan
