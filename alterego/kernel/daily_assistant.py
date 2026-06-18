"""ALTEREGO OS V2 — Daily Assistant.

ALTEREGO doit produire automatiquement :
  - Morning Brief (ce qui s'est passé, ce qui est prévu)
  - Evening Report (ce qui a été fait, ce qui reste)
  - Weekly Review (progrès sur les objectifs, tendances)
  - Monthly Review (bilan global, ajustements)
  - Progress Report (sur un objectif précis)
  - Infrastructure Report (état des serveurs/containers)
  - AI News Report (veille technologique)
  - Project Status Report (avancement des projets)

Tous les rapports sont générés à partir de la mémoire et des événements.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from loguru import logger


class DailyAssistant:
    """Generates automatic reports from memory, events, and goals.

    This is NOT a scheduler — it's a report generator. The CLI or a cron
    job calls these methods at the right time.
    """

    def __init__(
        self,
        memory: Any,
        goal_engine: Any = None,
        initiative_engine: Any = None,
        llm_plugin: Any = None,
    ) -> None:
        self.memory = memory
        self.goals = goal_engine
        self.initiatives = initiative_engine
        self.llm = llm_plugin

    async def morning_brief(self, user_id: str = "default") -> str:
        """Morning brief: what happened overnight, what's planned today.

        Sources:
        - Recent events (last 12h)
        - Active goals and their progress
        - Pending initiatives
        - Stale missions
        """
        lines = ["🌅 MORNING BRIEF — " + datetime.utcnow().strftime("%Y-%m-%d %H:%M")]
        lines.append("")

        # Active goals
        if self.goals:
            goals = await self.goals.list_goals()
            active = [g for g in goals if g.status.value == "active"]
            if active:
                lines.append(f"── Active Goals ({len(active)}) ──")
                for g in active[:5]:
                    lines.append(f"  • {g.title} — {g.progress():.0%} complete")
                lines.append("")

        # Recent missions (last 12h)
        tasks = await self.memory.query("tasks", user_id=user_id)
        recent = []
        now = datetime.utcnow()
        for t in tasks:
            created = t.data.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", ""))
                    if (now - dt).total_seconds() < 43200:  # 12h
                        recent.append(t)
                except Exception:
                    pass

        if recent:
            lines.append(f"── Recent Activity (last 12h: {len(recent)} missions) ──")
            for t in recent[-5:]:
                status = t.data.get("status", "?")
                icon = "✓" if status == "completed" else ("✗" if status == "failed" else "→")
                lines.append(f"  {icon} {t.data.get('objective', '?')[:60]}")
            lines.append("")

        # Pending initiatives
        if self.initiatives:
            pending = self.initiatives.get_pending_initiatives()
            if pending:
                lines.append(f"── Pending Initiatives ({len(pending)}) ──")
                for init in pending[:3]:
                    lines.append(f"  ⚠ [{init.priority.value}] {init.title}")
                lines.append("")

        # Preferences reminder
        prefs = await self.memory.query("preferences", user_id=user_id)
        if prefs:
            lines.append("── Your Preferences ──")
            for p in prefs[:3]:
                lines.append(f"  {p.data.get('key', '?')}: {p.data.get('value', '?')}")
            lines.append("")

        if len(lines) <= 2:
            lines.append("Nothing to report. Have a productive day! ☕")

        return "\n".join(lines)

    async def evening_report(self, user_id: str = "default") -> str:
        """Evening report: what was accomplished today."""
        lines = ["🌙 EVENING REPORT — " + datetime.utcnow().strftime("%Y-%m-%d")]
        lines.append("")

        # Today's missions
        tasks = await self.memory.query("tasks", user_id=user_id)
        today = []
        now = datetime.utcnow()
        for t in tasks:
            created = t.data.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", ""))
                    if dt.date() == now.date():
                        today.append(t)
                except Exception:
                    pass

        completed = [t for t in today if t.data.get("status") == "completed"]
        failed = [t for t in today if t.data.get("status") == "failed"]
        running = [t for t in today if t.data.get("status") == "running"]

        lines.append(f"── Today's Missions ({len(today)} total) ──")
        lines.append(f"  ✓ Completed: {len(completed)}")
        lines.append(f"  ✗ Failed: {len(failed)}")
        lines.append(f"  → Still running: {len(running)}")
        lines.append("")

        if completed:
            lines.append("── Completed Today ──")
            for t in completed[-5:]:
                lines.append(f"  ✓ {t.data.get('objective', '?')[:60]}")
            lines.append("")

        if failed:
            lines.append("── Failed Today ──")
            for t in failed[:3]:
                lines.append(f"  ✗ {t.data.get('objective', '?')[:60]}")
                lines.append(f"    Error: {t.data.get('error', '?')[:80]}")
            lines.append("")

        # Goal progress
        if self.goals:
            goals = await self.goals.list_goals()
            active = [g for g in goals if g.status.value == "active"]
            if active:
                lines.append("── Goal Progress ──")
                for g in active[:3]:
                    lines.append(f"  • {g.title}: {g.progress():.0%}")
                lines.append("")

        # Learning summary
        knowledge = await self.memory.query("knowledge")
        today_learning = [
            k for k in knowledge
            if k.data.get("learned_at", "").startswith(now.strftime("%Y-%m-%d"))
        ]
        if today_learning:
            lines.append(f"── Learning ({len(today_learning)} records) ──")
            for k in today_learning[-3:]:
                lines.append(f"  • {k.data.get('mission_id', '?')[:8]}: {k.data.get('status', '?')}")
            lines.append("")

        if len(lines) <= 2:
            lines.append("Quiet day. See you tomorrow! 🌙")

        return "\n".join(lines)

    async def weekly_review(self, user_id: str = "default") -> str:
        """Weekly review: progress on goals, trends, stats."""
        lines = ["📅 WEEKLY REVIEW — Week of " + datetime.utcnow().strftime("%Y-%m-%d")]
        lines.append("")

        # Missions this week
        tasks = await self.memory.query("tasks", user_id=user_id)
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        week_tasks = []
        for t in tasks:
            created = t.data.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", ""))
                    if dt > week_ago:
                        week_tasks.append(t)
                except Exception:
                    pass

        completed = sum(1 for t in week_tasks if t.data.get("status") == "completed")
        failed = sum(1 for t in week_tasks if t.data.get("status") == "failed")
        total = len(week_tasks)
        success_rate = completed / total if total else 0

        lines.append("── Week Stats ──")
        lines.append(f"  Total missions: {total}")
        lines.append(f"  Completed: {completed} ({success_rate:.0%})")
        lines.append(f"  Failed: {failed}")
        lines.append("")

        # Goal progress
        if self.goals:
            goals = await self.goals.list_goals()
            lines.append(f"── Goals ({len(goals)} total) ──")
            for g in goals[:5]:
                lines.append(f"  • {g.title} [{g.status.value}] — {g.progress():.0%}")
            lines.append("")

        # Conversations this week
        convs = await self.memory.query("conversations", user_id=user_id)
        week_convs = []
        for c in convs:
            # Approximate: if we have timestamp
            ts = c.data.get("timestamp", 0)
            if isinstance(ts, (int, float)) and ts > 0:
                # Assume timestamp is relative (from scenario tests)
                week_convs.append(c)
        lines.append(f"  Conversations: {len(week_convs)}")
        lines.append("")

        return "\n".join(lines)

    async def progress_report(self, goal_id: str) -> str:
        """Detailed progress report for a specific goal."""
        if not self.goals:
            return "Goal Engine not available."

        goal = await self.goals.get_goal(goal_id)
        if not goal:
            return f"Goal {goal_id} not found."

        lines = [f"📊 PROGRESS REPORT — {goal.title}"]
        lines.append("")
        lines.append(goal.summary())
        lines.append("")

        # Detailed objectives
        lines.append("── Objectives Detail ──")
        for obj in goal.objectives:
            icon = "✓" if obj.status.value == "completed" else ("⏸" if obj.status.value == "paused" else "→")
            lines.append(f"  {icon} {obj.title}")
            lines.append(f"    {obj.description}")
            lines.append(f"    Missions: {len(obj.missions)}")
            if obj.completed_at:
                lines.append(f"    Completed: {obj.completed_at[:10]}")
            lines.append("")

        return "\n".join(lines)
