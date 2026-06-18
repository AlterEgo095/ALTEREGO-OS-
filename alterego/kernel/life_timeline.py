"""ALTEREGO OS V2.1 — Life Timeline.

Tous les événements importants sont enregistrés automatiquement :
  Mission créée, Mission terminée, Objectif atteint, Projet créé,
  Déploiement, Commit, Sauvegarde, Erreur, Décision, Rapport,
  Apprentissage, Nouvelle habitude, Nouvelle préférence.

La timeline devient l'historique vivant d'ALTEREGO.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger


class LifeTimeline:
    """Records and queries important life events.

    Events are stored in Memory under 'documents' entity type
    (reused as a general-purpose store) with a 'timeline' marker.

    The timeline is append-only — events can't be deleted (only archived).
    """

    def __init__(self, memory: Any, event_bus: Any = None) -> None:
        self.memory = memory
        self.bus = event_bus

    async def record(
        self,
        event_type: str,
        title: str,
        description: str = "",
        severity: str = "info",  # info, success, warning, error, critical
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Record a timeline event.

        Args:
            event_type: "mission_created", "mission_completed", "goal_reached", etc.
            title: Short title
            description: Longer description
            severity: info/success/warning/error/critical
            source: Which component emitted this
            metadata: Additional structured data
        """
        record_id = await self.memory.put("documents", {
            "timeline": True,
            "event_type": event_type,
            "title": title,
            "description": description,
            "severity": severity,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        })

        # Also publish on event bus
        if self.bus:
            await self.bus.publish(
                f"timeline.{event_type}",
                {"title": title, "severity": severity, "timeline_id": record_id},
                source=source or "timeline",
            )

        logger.debug(f"Timeline: recorded '{event_type}' — {title}")
        return record_id

    async def get_events(
        self,
        event_type: str | None = None,
        severity: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query timeline events with optional filters."""
        records = await self.memory.query("documents")
        events = []
        for r in records:
            if not r.data.get("timeline"):
                continue

            # Filter by event_type
            if event_type and r.data.get("event_type") != event_type:
                continue

            # Filter by severity
            if severity and r.data.get("severity") != severity:
                continue

            # Filter by date range
            ts = r.data.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", ""))
                    if since and dt < since:
                        continue
                    if until and dt > until:
                        continue
                except Exception:
                    pass

            events.append(r.data)

        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return events[:limit]

    async def get_today(self) -> list[dict[str, Any]]:
        """Get all events from today."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.get_events(since=today_start, limit=50)

    async def get_recent(self, hours: int = 24, limit: int = 50) -> list[dict[str, Any]]:
        """Get events from the last N hours."""
        since = datetime.utcnow() - timedelta(hours=hours)
        return await self.get_events(since=since, limit=limit)

    async def get_critical(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get all critical/error events."""
        records = await self.memory.query("documents")
        events = []
        for r in records:
            if not r.data.get("timeline"):
                continue
            if r.data.get("severity") in ("error", "critical"):
                events.append(r.data)
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return events[:limit]

    async def summary(self, days: int = 7) -> str:
        """Human-readable timeline summary for the last N days."""
        since = datetime.utcnow() - timedelta(days=days)
        events = await self.get_events(since=since, limit=200)

        if not events:
            return f"No timeline events in the last {days} days."

        # Count by type
        type_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        for e in events:
            et = e.get("event_type", "unknown")
            type_counts[et] = type_counts.get(et, 0) + 1
            sv = e.get("severity", "info")
            severity_counts[sv] = severity_counts.get(sv, 0) + 1

        lines = [f"📅 Life Timeline — Last {days} days ({len(events)} events)", ""]

        # Severity summary
        lines.append("── By Severity ──")
        for sv in ["critical", "error", "warning", "success", "info"]:
            count = severity_counts.get(sv, 0)
            if count:
                icon = {"critical": "🔴", "error": "❌", "warning": "⚠️", "success": "✅", "info": "ℹ️"}.get(sv, "•")
                lines.append(f"  {icon} {sv}: {count}")
        lines.append("")

        # Type summary
        lines.append("── By Type ──")
        for et, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {et}: {count}")
        lines.append("")

        # Last 10 events
        lines.append("── Recent Events ──")
        for e in events[:10]:
            icon = {"critical": "🔴", "error": "❌", "warning": "⚠️", "success": "✅", "info": "ℹ️"}.get(e.get("severity", "info"), "•")
            ts = e.get("timestamp", "")[:19]
            lines.append(f"  {icon} [{ts}] {e.get('title', '?')[:60]}")

        return "\n".join(lines)
