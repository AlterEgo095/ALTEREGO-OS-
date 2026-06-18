"""ALTEREGO OS V2 — Context Engine.

ALTEREGO doit comprendre en permanence :
  - le projet actuellement actif
  - le serveur concerné
  - le dépôt concerné
  - la conversation précédente
  - les préférences utilisateur
  - les habitudes
  - les objectifs en cours

Aucune perte de contexte.

Le Context Engine maintient un "contexte courant" qui est injecté
dans chaque mission. Il se met à jour automatiquement en fonction
des missions, des conversations, et des actions de l'utilisateur.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from loguru import logger


class ContextEngine:
    """Maintains a persistent context that spans conversations.

    The context includes:
    - active_goal: the goal currently being worked on
    - active_project: the project currently in focus
    - active_server: the server currently being managed
    - active_repo: the repository currently being analyzed
    - recent_conversations: last N conversation summaries
    - user_preferences: all known preferences
    - active_initiatives: pending initiatives
    - working_directory: where the user is working

    The context is injected into the Decision Engine so the Planner
    can produce better-informed plans.
    """

    MAX_RECENT_CONVERSATIONS = 5

    def __init__(self, memory: Any, digital_twin: Any = None, goal_engine: Any = None) -> None:
        self.memory = memory
        self.twin = digital_twin
        self.goals = goal_engine

    async def get_context(self, user_id: str = "default") -> dict[str, Any]:
        """Build the current context for a user.

        This is called by the Decision Engine before planning.
        """
        context = {
            "user_id": user_id,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # 1. Active goals
        if self.goals:
            goals = await self.goals.list_goals()
            active_goals = [g for g in goals if g.status.value == "active"]
            if active_goals:
                context["active_goals"] = [
                    {"id": g.id, "title": g.title, "progress": g.progress(), "priority": g.priority}
                    for g in active_goals[:3]
                ]
                # The most recent active goal is the "current" one
                context["current_goal"] = active_goals[0].title

        # 2. Recent conversations (context continuity)
        convs = await self.memory.query("conversations", user_id=user_id)
        recent = convs[-self.MAX_RECENT_CONVERSATIONS:] if convs else []
        context["recent_conversations"] = [
            {
                "role": c.data.get("role", "?"),
                "content": c.data.get("content", "")[:100],
                "objective": c.data.get("objective", ""),
            }
            for c in recent
        ]

        # 3. User preferences
        prefs = await self.memory.query("preferences", user_id=user_id)
        context["preferences"] = {
            p.data.get("key", "?"): p.data.get("value", "?")
            for p in prefs
        }

        # 4. Known projects
        projects = await self.memory.query("projects", user_id=user_id)
        context["known_projects"] = [p.data.get("name", "?") for p in projects]

        # 5. Known servers
        servers = await self.memory.query("servers", user_id=user_id)
        context["known_servers"] = [
            {"name": s.data.get("name", "?"), "host": s.data.get("host", "?")}
            for s in servers
        ]

        # 6. Recent missions (last 5)
        tasks = await self.memory.query("tasks", user_id=user_id)
        recent_tasks = tasks[-5:] if tasks else []
        context["recent_missions"] = [
            {
                "id": t.id[:8],
                "objective": t.data.get("objective", "?")[:60],
                "status": t.data.get("status", "?"),
            }
            for t in recent_tasks
        ]

        # 7. Digital Twin info
        if self.twin:
            twin_summary = await self.twin.get_profile_summary()
            context["twin"] = {
                "missions_total": twin_summary.get("missions_total", 0),
                "success_rate": twin_summary.get("success_rate", 0),
            }

        return context

    async def get_context_summary(self, user_id: str = "default") -> str:
        """Human-readable context summary for the Decision Engine / LLM.

        This is injected into the Planner prompt so the LLM knows:
        - what the user is working on
        - what happened recently
        - what preferences the user has
        """
        ctx = await self.get_context(user_id)
        lines = []

        if ctx.get("current_goal"):
            lines.append(f"Current goal: {ctx['current_goal']}")

        if ctx.get("recent_conversations"):
            lines.append("Recent context:")
            for c in ctx["recent_conversations"][-3:]:
                role = c.get("role", "?")
                content = c.get("content", "?")[:60]
                lines.append(f"  [{role}] {content}")

        if ctx.get("preferences"):
            pref_str = ", ".join(f"{k}={v}" for k, v in ctx["preferences"].items())
            lines.append(f"User preferences: {pref_str}")

        if ctx.get("known_projects"):
            lines.append(f"Known projects: {', '.join(ctx['known_projects'])}")

        if ctx.get("known_servers"):
            servers_str = ", ".join(s["name"] for s in ctx["known_servers"])
            lines.append(f"Known servers: {servers_str}")

        if ctx.get("recent_missions"):
            lines.append("Recent missions:")
            for m in ctx["recent_missions"][-3:]:
                lines.append(f"  {m['status']}: {m['objective']}")

        return "\n".join(lines) if lines else "(no context available)"

    async def update_active_project(self, user_id: str, project_name: str) -> None:
        """Set the currently active project."""
        await self.memory.put("preferences", {
            "user_id": user_id,
            "key": "active_project",
            "value": project_name,
            "inferred": True,
            "updated_at": datetime.utcnow().isoformat(),
        })
        logger.info(f"ContextEngine: active project set to '{project_name}'")

    async def update_active_server(self, user_id: str, server_name: str) -> None:
        """Set the currently active server."""
        await self.memory.put("preferences", {
            "user_id": user_id,
            "key": "active_server",
            "value": server_name,
            "inferred": True,
            "updated_at": datetime.utcnow().isoformat(),
        })
        logger.info(f"ContextEngine: active server set to '{server_name}'")

    async def clear_context(self, user_id: str = "default") -> None:
        """Clear the active project/server context (e.g. when switching tasks)."""
        prefs = await self.memory.query("preferences", user_id=user_id)
        for p in prefs:
            if p.data.get("key") in ("active_project", "active_server"):
                await self.memory.update("preferences", p.id, {
                    "value": None,
                    "updated_at": datetime.utcnow().isoformat(),
                })
        logger.info(f"ContextEngine: context cleared for user {user_id}")
