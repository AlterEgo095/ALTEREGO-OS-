"""ALTEREGO OS — Planner.

Decomposes a mission into a flat list of tasks (V1: no DAG, just ordered steps).
V2 will produce a real DAG with dependencies.

The Planner uses the LLM plugin to break down the objective, given the list
of available capabilities from the CapabilityRegistry.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel

from alterego.kernel.base import Mission
from alterego.kernel.capability_registry import CapabilityRegistry


class Task(BaseModel):
    """A single step in a mission plan."""
    step: int
    description: str
    capability: str  # e.g. "github", "llm.chat"
    method: str = ""  # e.g. "clone", "chat"
    params: dict[str, Any] = {}


class Planner:
    """Plans missions by decomposing objectives into tasks.

    V1 strategy:
      1. If the objective is a no-op (no external capability needed), return a single
         LLM task that answers directly.
      2. Otherwise, ask the LLM to produce a JSON plan using the available capabilities.
    """

    PLANNER_PROMPT = """You are the Planner of ALTEREGO OS, an AI Operating System.
Given a user objective and the list of available capabilities, produce a JSON plan.

Available capabilities:
{capabilities}

Output STRICT JSON in this exact format (no markdown, no explanation):
{{
  "tasks": [
    {{
      "step": 1,
      "description": "what to do",
      "capability": "one of the capabilities above",
      "method": "method name (e.g. clone, chat, exec, query)",
      "params": {{}}
    }}
  ]
}}

Rules:
- Each task MUST use one of the listed capabilities.
- Keep plans short (3-6 tasks max for V1).
- The `params` dict must contain concrete values (no placeholders).
- If the objective is purely conversational (just answer a question), use one task with capability=llm.chat.
"""

    def __init__(self, capability_registry: CapabilityRegistry, llm_plugin: Any) -> None:
        self.capability_registry = capability_registry
        self.llm_plugin = llm_plugin

    async def plan(self, mission: Mission) -> list[Task]:
        """Produce a list of tasks for the given mission."""
        caps_description = self.capability_registry.describe() or "(no capabilities registered)"
        prompt = self.PLANNER_PROMPT.format(capabilities=caps_description)
        user_msg = f"Objective: {mission.objective}"

        logger.info(f"planning mission {mission.id}: {mission.objective[:80]}")

        # Use LLM plugin to produce the plan
        try:
            raw = await self.llm_plugin.call("chat", {
                "system": prompt,
                "user": user_msg,
                "temperature": 0.2,
            })
        except Exception as e:
            logger.error(f"planner LLM call failed: {e}")
            # Fallback: single LLM task that answers directly
            return [Task(
                step=1,
                description="Answer the user directly (fallback after planner failure)",
                capability="llm.chat",
                method="chat",
                params={"system": "You are a helpful assistant.", "user": mission.objective},
            )]

        # Parse the JSON plan
        plan = self._parse_plan(raw)
        if not plan:
            logger.warning("planner produced empty/invalid plan; fallback to direct LLM")
            return [Task(
                step=1,
                description="Answer the user directly",
                capability="llm.chat",
                method="chat",
                params={"system": "You are a helpful assistant.", "user": mission.objective},
            )]

        return plan

    def _parse_plan(self, raw: Any) -> Optional[list[Task]]:
        """Parse the LLM output into a list of Task. Returns None on failure.

        Handles multiple response formats:
        - {"content": '{"tasks": [...]}'}  (LLM plugin wraps in content)
        - {"tasks": [...]}                 (direct dict)
        - '{"tasks": [...]}'               (raw JSON string)
        """
        # Extract the actual content if wrapped in {"content": ...}
        if isinstance(raw, dict):
            if "tasks" in raw:
                tasks_data = raw["tasks"]
            elif "content" in raw:
                # LLM plugin returns {"content": "..."} — content may be JSON string
                content = raw["content"]
                if isinstance(content, str):
                    raw = content  # fall through to string parsing
                elif isinstance(content, dict) and "tasks" in content:
                    tasks_data = content["tasks"]
                else:
                    return None
            else:
                return None
        else:
            raw = str(raw) if raw else ""

        if isinstance(raw, str):
            try:
                tasks_data = json.loads(raw).get("tasks", [])
            except json.JSONDecodeError:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    try:
                        tasks_data = json.loads(raw[start:end]).get("tasks", [])
                    except json.JSONDecodeError:
                        return None
                else:
                    return None

        tasks = []
        for i, t in enumerate(tasks_data, start=1):
            try:
                tasks.append(Task(
                    step=t.get("step", i),
                    description=t.get("description", ""),
                    capability=t.get("capability", "llm.chat"),
                    method=t.get("method", ""),
                    params=t.get("params", {}),
                ))
            except Exception as e:
                logger.warning(f"failed to parse task {i}: {e}")
        return tasks if tasks else None
