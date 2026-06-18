"""ALTEREGO OS — Decision Engine.

The Decision Engine sits between the Mission Engine and the Planner. It:
  1. Analyzes the mission objective (extract intent, context).
  2. Pulls relevant context from Memory (conversations, projects, ...).
  3. Forwards to the Planner with the ORIGINAL objective (not enriched).

V1.1: The Planner receives the raw user objective — not the enriched version.
The intent and context are logged for debugging but NOT injected into the
planner prompt (they confuse the LLM into answering conversationally instead
of producing JSON).
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
        """Analyze the mission, then produce a plan.

        V1.1: The Planner receives the ORIGINAL user objective, not an
        enriched version. The intent extraction is logged but NOT passed
        to the Planner (it was confusing the LLM into answering
        conversationally instead of producing JSON).
        """
        # 1. Extract intent (for logging/debugging only — NOT passed to Planner)
        try:
            intent = await self.llm_plugin.call("chat", {
                "system": self.INTENT_PROMPT,
                "user": mission.objective,
                "temperature": 0.0,
            })
            if isinstance(intent, dict):
                intent = intent.get("content", str(intent))
            logger.info(f"mission {mission.id} intent: {str(intent)[:100]}")
        except Exception as e:
            logger.warning(f"intent extraction failed ({e}); using raw objective")
            intent = mission.objective

        # 2. Pull recent conversations from memory (for logging only)
        recent = await self.memory.query("conversations", user_id=mission.user_id)
        if recent:
            logger.debug(f"mission {mission.id} has {len(recent)} prior conversations in context")

        # 3. Plan — pass the ORIGINAL objective to the Planner
        # Do NOT enrich mission.objective — the Planner needs the raw user text
        plan = await self.planner.plan(mission)
        logger.info(f"mission {mission.id} plan: {len(plan)} tasks")
        return plan
