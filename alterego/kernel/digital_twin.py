"""ALTEREGO OS — Digital Twin (Règle 9).

ALTEREGO doit apprendre à connaître l'utilisateur :
  - habitudes
  - projets
  - entreprises
  - serveurs
  - préférences
  - documents
  - méthodes de travail
  - objectifs
  - historique

Cette mémoire constitue progressivement le cerveau numérique externe.

Le Digital Twin est une couche au-dessus de Memory qui structure
les informations sur l'utilisateur en un profil cohérent.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger


class DigitalTwin:
    """Structured user profile that grows with usage.

    The Digital Twin is NOT a separate database — it's a view layer
    on top of Memory that aggregates and structures user information.

    It provides:
    - profile_summary() — who the user is (inferred + explicit)
    - get_habits() — patterns detected from behavior
    - get_preferences() — explicit + inferred preferences
    - get_projects() — known projects
    - get_servers() — known servers/infrastructure
    - get_objectives() — current goals
    - update_from_mission() — learn from each mission outcome
    """

    def __init__(self, memory: Any, user_id: str = "default") -> None:
        self.memory = memory
        self.user_id = user_id

    async def get_profile_summary(self) -> dict[str, Any]:
        """Get a complete profile summary for the user."""
        prefs = await self.get_preferences()
        projects = await self.get_projects()
        servers = await self.get_servers()
        objectives = await self.get_objectives()
        habits = await self.get_habits()
        conversations = await self.memory.query("conversations", user_id=self.user_id)
        missions = await self.memory.query("tasks", user_id=self.user_id)

        completed = sum(1 for m in missions if m.data.get("status") == "completed")
        failed = sum(1 for m in missions if m.data.get("status") == "failed")

        return {
            "user_id": self.user_id,
            "conversations_count": len(conversations),
            "missions_total": len(missions),
            "missions_completed": completed,
            "missions_failed": failed,
            "success_rate": completed / len(missions) if missions else 0,
            "preferences": prefs,
            "projects": projects,
            "servers": servers,
            "objectives": objectives,
            "habits": habits,
            "profile_generated_at": datetime.utcnow().isoformat(),
        }

    async def get_preferences(self) -> dict[str, Any]:
        """Get all preferences (explicit + inferred)."""
        prefs = await self.memory.query("preferences", user_id=self.user_id)
        result = {}
        for p in prefs:
            result[p.data.get("key", "")] = {
                "value": p.data.get("value"),
                "inferred": p.data.get("inferred", False),
            }
        return result

    async def get_projects(self) -> list[dict[str, Any]]:
        """Get all known projects."""
        projects = await self.memory.query("projects", user_id=self.user_id)
        return [p.data for p in projects]

    async def get_servers(self) -> list[dict[str, Any]]:
        """Get all known servers/infrastructure."""
        servers = await self.memory.query("servers", user_id=self.user_id)
        return [s.data for s in servers]

    async def get_objectives(self) -> list[dict[str, Any]]:
        """Get current objectives (from knowledge entity)."""
        knowledge = await self.memory.query("knowledge")
        return [
            k.data for k in knowledge
            if k.data.get("type") == "objective"
        ]

    async def get_habits(self) -> list[dict[str, Any]]:
        """Get detected habits from Learning Engine."""
        knowledge = await self.memory.query("knowledge")
        return [
            k.data for k in knowledge
            if k.data.get("type") == "user_feedback" or k.data.get("type") == "initiative"
        ][:10]  # last 10

    async def set_preference(self, key: str, value: Any, inferred: bool = False) -> None:
        """Set or update a preference."""
        existing = await self.memory.query("preferences", user_id=self.user_id, key=key)
        if existing:
            await self.memory.update("preferences", existing[0].id, {
                "value": value,
                "inferred": inferred,
                "updated_at": datetime.utcnow().isoformat(),
            })
        else:
            await self.memory.put("preferences", {
                "user_id": self.user_id,
                "key": key,
                "value": value,
                "inferred": inferred,
                "set_at": datetime.utcnow().isoformat(),
            })
        logger.info(f"DigitalTwin: preference {key}={value} (inferred={inferred})")

    async def register_project(self, name: str, **details: Any) -> str:
        """Register a new project."""
        record_id = await self.memory.put("projects", {
            "user_id": self.user_id,
            "name": name,
            "registered_at": datetime.utcnow().isoformat(),
            **details,
        })
        logger.info(f"DigitalTwin: registered project '{name}'")
        return record_id

    async def register_server(self, name: str, host: str, **details: Any) -> str:
        """Register a new server."""
        record_id = await self.memory.put("servers", {
            "user_id": self.user_id,
            "name": name,
            "host": host,
            "registered_at": datetime.utcnow().isoformat(),
            **details,
        })
        logger.info(f"DigitalTwin: registered server '{name}' ({host})")
        return record_id

    async def set_objective(self, objective: str, **details: Any) -> str:
        """Record a user objective."""
        record_id = await self.memory.put("knowledge", {
            "type": "objective",
            "user_id": self.user_id,
            "objective": objective,
            "set_at": datetime.utcnow().isoformat(),
            **details,
        })
        logger.info(f"DigitalTwin: recorded objective '{objective[:60]}'")
        return record_id

    async def update_from_mission(self, mission: Any) -> None:
        """Learn from a completed mission — update the twin.

        Called by LearningEngine after each mission.
        """
        # Infer language preference from mission objective
        obj = mission.objective.lower() if hasattr(mission, "objective") else str(mission.get("objective", "")).lower()
        if any(w in obj for w in ["bonjour", "salut", "crée", "vérifie", "analyse", "merci"]):
            await self.set_preference("language", "fr", inferred=True)
        elif any(w in obj for w in ["hello", "create", "check", "analyze", "thanks"]):
            await self.set_preference("language", "en", inferred=True)

        # Track mission topics for habit detection
        if hasattr(mission, "status"):
            if mission.status.value == "completed":
                await self.set_preference("last_successful_objective", mission.objective[:100], inferred=True)

    async def describe(self) -> str:
        """Human-readable description of the user's digital twin."""
        profile = await self.get_profile_summary()
        lines = [
            f"Digital Twin — User: {self.user_id}",
            f"  Conversations: {profile['conversations_count']}",
            f"  Missions: {profile['missions_total']} (✓{profile['missions_completed']} ✗{profile['missions_failed']})",
            f"  Success rate: {profile['success_rate']:.0%}",
            f"  Projects: {len(profile['projects'])}",
            f"  Servers: {len(profile['servers'])}",
            f"  Preferences: {len(profile['preferences'])}",
            f"  Objectives: {len(profile['objectives'])}",
        ]
        if profile["preferences"]:
            lines.append("  ── Preferences ──")
            for k, v in profile["preferences"].items():
                inferred_tag = " (inferred)" if v.get("inferred") else ""
                lines.append(f"    {k}: {v['value']}{inferred_tag}")
        if profile["projects"]:
            lines.append("  ── Projects ──")
            for p in profile["projects"]:
                lines.append(f"    {p.get('name', '?')}")
        if profile["servers"]:
            lines.append("  ── Servers ──")
            for s in profile["servers"]:
                lines.append(f"    {s.get('name', '?')} ({s.get('host', '?')})")
        return "\n".join(lines)
