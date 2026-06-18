"""ALTEREGO OS — Chief Of Staff.

The only component the user talks to. Everything else is invisible.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from loguru import logger

from alterego.kernel.base import Mission
from alterego.kernel.event_bus import EventBus
from alterego.kernel.memory import Memory
from alterego.kernel.mission_engine import MissionEngine


class ChiefOfStaff:
    """Conversational entry point. Translates natural language into missions."""

    def __init__(
        self,
        mission_engine: MissionEngine,
        memory: Memory,
        event_bus: EventBus,
    ) -> None:
        self.mission_engine = mission_engine
        self.memory = memory
        self.event_bus = event_bus

    async def chat(self, message: str, user_id: str = "default") -> str:
        """Receive a natural-language message, return a natural-language response.

        V1: every message becomes a mission. The mission result is rendered
        back as a string. V2 will add conversation memory and clarification
        rounds.
        """
        logger.info(f"CoS received message from {user_id}: {message[:80]}")

        # Save the user message as a conversation record
        conv_id = await self.memory.put(
            "conversations",
            {"user_id": user_id, "role": "user", "content": message, "objective": message},
        )

        # Create a mission
        mission = await self.mission_engine.create(message, user_id=user_id)

        # Run it
        mission = await self.mission_engine.run(mission)

        # Render the result as a string response
        response = self._render(mission)

        # Save our response
        await self.memory.put(
            "conversations",
            {"user_id": user_id, "role": "assistant", "content": response, "mission_id": mission.id},
        )

        return response

    def _render(self, mission: Mission) -> str:
        """Render the mission result as a user-facing string."""
        if mission.status.value == "failed":
            return f"❌ Mission échouée : {mission.error}"

        if not mission.result:
            return "✓ Mission terminée (aucun résultat)"

        lines = [f"✓ Mission terminée ({len(mission.result)} étapes) :\n"]
        for r in mission.result:
            step = r.get("step", "?")
            desc = r.get("description", "")
            result = r.get("result")
            lines.append(f"  {step}. {desc}")
            # Render the result compactly
            if isinstance(result, str):
                lines.append(f"     → {result[:300]}")
            elif isinstance(result, dict):
                # LLM responses often return {"content": "..."}
                content = result.get("content") or result.get("text") or str(result)
                if isinstance(content, str):
                    lines.append(f"     → {content[:400]}")
                else:
                    lines.append(f"     → {str(content)[:300]}")
            else:
                lines.append(f"     → {str(result)[:300]}")
        return "\n".join(lines)
