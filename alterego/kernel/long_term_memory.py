"""ALTEREGO OS V2.1 — Long Term Memory.

Mémoire persistante capable de raisonner sur plusieurs mois.

Permet :
  - Comparer deux périodes
  - Comparer deux versions d'un projet
  - Retrouver une ancienne idée/discussion/décision
  - Construire des synthèses historiques
  - Détecter des tendances

Construit au-dessus de Memory + LifeTimeline.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger


class LongTermMemory:
    """Long-term reasoning over weeks and months of data.

    Provides temporal queries, comparisons, and trend detection
    across the full history of conversations, missions, and events.
    """

    def __init__(self, memory: Any, timeline: Any = None) -> None:
        self.memory = memory
        self.timeline = timeline

    async def search_conversations(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search past conversations by keyword.

        Simple keyword matching (V1). V2 will use vector search.
        """
        records = await self.memory.query("conversations")
        query_lower = query.lower()
        results = []
        for r in records:
            content = r.data.get("content", "").lower()
            objective = r.data.get("objective", "").lower()
            if query_lower in content or query_lower in objective:
                results.append({
                    "id": r.id,
                    "role": r.data.get("role", "?"),
                    "content": r.data.get("content", "")[:200],
                    "objective": r.data.get("objective", ""),
                    "timestamp": r.data.get("timestamp", ""),
                })
        return results[:limit]

    async def search_missions(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search past missions by keyword in objective."""
        records = await self.memory.query("tasks")
        query_lower = query.lower()
        results = []
        for r in records:
            obj = r.data.get("objective", "").lower()
            if query_lower in obj:
                results.append({
                    "id": r.id[:8],
                    "objective": r.data.get("objective", "")[:100],
                    "status": r.data.get("status", "?"),
                    "created_at": r.data.get("created_at", ""),
                })
        return results[:limit]

    async def search_decisions(self, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
        """Search past decisions (from Digital Twin V2)."""
        records = await self.memory.query("knowledge")
        query_lower = query.lower() if query else ""
        results = []
        for r in records:
            if r.data.get("twin_type") != "decision":
                continue
            if query_lower and query_lower not in r.data.get("name", "").lower() and query_lower not in r.data.get("description", "").lower():
                continue
            results.append(r.data)
        return results[:limit]

    async def compare_periods(
        self,
        period1_start: datetime,
        period1_end: datetime,
        period2_start: datetime,
        period2_end: datetime,
    ) -> dict[str, Any]:
        """Compare two time periods (missions, conversations, events).

        Returns stats for each period and a diff.
        """
        p1 = await self._period_stats(period1_start, period1_end)
        p2 = await self._period_stats(period2_start, period2_end)

        return {
            "period1": {"start": period1_start.isoformat(), "end": period1_end.isoformat(), **p1},
            "period2": {"start": period2_start.isoformat(), "end": period2_end.isoformat(), **p2},
            "diff": {
                "missions": p2["missions_total"] - p1["missions_total"],
                "conversations": p2["conversations"] - p1["conversations"],
                "success_rate": p2["success_rate"] - p1["success_rate"],
            },
        }

    async def _period_stats(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Get stats for a time period."""
        tasks = await self.memory.query("tasks")
        convs = await self.memory.query("conversations")

        period_tasks = []
        period_convs = []
        for t in tasks:
            ts = t.data.get("created_at", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", ""))
                    if start <= dt <= end:
                        period_tasks.append(t)
                except Exception:
                    pass

        for c in convs:
            ts = c.data.get("timestamp", "")
            if isinstance(ts, str) and ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", ""))
                    if start <= dt <= end:
                        period_convs.append(c)
                except Exception:
                    pass

        completed = sum(1 for t in period_tasks if t.data.get("status") == "completed")
        failed = sum(1 for t in period_tasks if t.data.get("status") == "failed")
        total = len(period_tasks)

        return {
            "missions_total": total,
            "missions_completed": completed,
            "missions_failed": failed,
            "success_rate": completed / total if total else 0,
            "conversations": len(period_convs),
        }

    async def detect_trends(self, days: int = 30) -> dict[str, Any]:
        """Detect trends over the last N days."""
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=days)

        recent = await self._period_stats(week_ago, now)
        older = await self._period_stats(month_ago, week_ago)

        trends = {
            "period": f"Last {days} days vs previous week",
            "mission_volume_trend": "increasing" if recent["missions_total"] > older["missions_total"] else "decreasing" if recent["missions_total"] < older["missions_total"] else "stable",
            "success_rate_trend": "improving" if recent["success_rate"] > older["success_rate"] else "declining" if recent["success_rate"] < older["success_rate"] else "stable",
            "conversation_trend": "increasing" if recent["conversations"] > older["conversations"] else "decreasing" if recent["conversations"] < older["conversations"] else "stable",
            "recent_stats": recent,
            "comparison_stats": older,
        }
        return trends

    async def find_old_idea(self, keyword: str) -> str:
        """Find an old idea by searching conversations and decisions.

        Returns a human-readable summary of what was found.
        """
        convs = await self.search_conversations(keyword)
        decisions = await self.search_decisions(keyword)
        missions = await self.search_missions(keyword)

        lines = [f"🔍 Search for '{keyword}':"]
        if convs:
            lines.append(f"\n  Conversations ({len(convs)}):")
            for c in convs[:3]:
                lines.append(f"    [{c.get('role', '?')}] {c.get('content', '?')[:80]}")
        if decisions:
            lines.append(f"\n  Decisions ({len(decisions)}):")
            for d in decisions[:3]:
                lines.append(f"    • {d.get('name', '?')}: {d.get('description', '?')[:80]}")
        if missions:
            lines.append(f"\n  Missions ({len(missions)}):")
            for m in missions[:3]:
                lines.append(f"    {m.get('status', '?')}: {m.get('objective', '?')[:80]}")

        if not convs and not decisions and not missions:
            lines.append("  No results found.")

        return "\n".join(lines)

    async def historical_summary(self, days: int = 30) -> str:
        """Generate a historical synthesis over N days."""
        trends = await self.detect_trends(days)
        recent_tasks = await self.memory.query("tasks")
        recent_convs = await self.memory.query("conversations")

        lines = [f"📊 Historical Summary — Last {days} days", ""]
        lines.append(f"  Total missions: {len(recent_tasks)}")
        lines.append(f"  Total conversations: {len(recent_convs)}")
        lines.append(f"  Mission volume: {trends['mission_volume_trend']}")
        lines.append(f"  Success rate: {trends['success_rate_trend']}")
        lines.append(f"  Conversation activity: {trends['conversation_trend']}")

        return "\n".join(lines)
