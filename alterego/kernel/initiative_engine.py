"""ALTEREGO OS — Initiative Engine (Règle 10).

ALTEREGO ne doit pas seulement attendre des ordres.
Il doit détecter :
  - opportunités (nouveautés tech, repos trending, prix LLM)
  - anomalies (serveur down, CPU critique, disque plein, container crashed)
  - mises à jour (deps obsolètes, security advisories, forks de licencing)
  - risques (secrets dans git history, dépendances vulnérables)
  - améliorations (TODO/FIXME accumulés, tests manquants, doc absente)

puis proposer ou créer automatiquement des missions.

Le Initiative Engine tourne en background (cron ou loop) et :
  1. Scanne les sources configurées (memory, repos surveillés, serveurs)
  2. Détecte les signaux (patterns, thresholds, changements)
  3. Crée des missions proactives (avec confidence + policy check)
  4. Notifie le Chief Of Staff qui décide si l'utilisateur doit être alerté

V1.3 : implémente 5 detectors de base + scan loop.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from loguru import logger


class InitiativeType(str, Enum):
    OPPORTUNITY = "opportunity"      # something good to explore
    ANOMALY = "anomaly"              # something wrong to fix
    UPDATE = "update"                # something changed to review
    RISK = "risk"                    # something dangerous to address
    IMPROVEMENT = "improvement"      # something to make better


class InitiativePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Initiative:
    """A proactive initiative detected by the engine."""
    id: str
    type: InitiativeType
    priority: InitiativePriority
    title: str
    description: str
    suggested_mission: str = ""  # natural language objective for a mission
    source: str = ""  # what detector found this
    detected_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    auto_created_mission: bool = False  # was a mission auto-created?
    user_notified: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "suggested_mission": self.suggested_mission,
            "source": self.source,
            "detected_at": self.detected_at,
            "auto_created_mission": self.auto_created_mission,
            "user_notified": self.user_notified,
            "metadata": self.metadata,
        }


class InitiativeEngine:
    """Scans for opportunities, anomalies, and risks — creates missions proactively.

    Detectors V1.3:
    1. MemoryGrowthDetector — tracks if memory is growing too fast (possible leak)
    2. StaleMissionDetector — finds missions stuck in 'running' for too long
    3. FailedMissionPatternDetector — detects recurring failure patterns
    4. UserHabitDetector — infers habits from conversation patterns
    5. KnowledgeGapDetector — finds entities in memory with stale/missing data

    Each detector returns a list of Initiatives. The engine aggregates them,
    deduplicates, and optionally creates missions via the Chief Of Staff.
    """

    def __init__(
        self,
        memory: Any,
        event_bus: Any = None,
        chief_of_staff: Any = None,
        auto_create_missions: bool = False,  # V1.3: conservative — don't auto-create
    ) -> None:
        self.memory = memory
        self.bus = event_bus
        self.cos = chief_of_staff
        self.auto_create = auto_create_missions
        self._detectors: list[Callable] = []
        self._initiatives: list[Initiative] = []
        self._scan_count = 0

        # Register built-in detectors
        self._detectors.append(self._detect_stale_missions)
        self._detectors.append(self._detect_failed_patterns)
        self._detectors.append(self._detect_user_habits)
        self._detectors.append(self._detect_knowledge_gaps)
        self._detectors.append(self._detect_memory_growth)

    async def scan(self) -> list[Initiative]:
        """Run all detectors and return aggregated initiatives.

        This is the main entry point. Call periodically (e.g. every 5 min)
        or on-demand.
        """
        self._scan_count += 1
        logger.info(f"InitiativeEngine: scan #{self._scan_count} starting...")
        all_initiatives = []

        for detector in self._detectors:
            try:
                found = await detector()
                all_initiatives.extend(found)
                if found:
                    logger.info(f"InitiativeEngine: {detector.__name__} found {len(found)} initiative(s)")
            except Exception as e:
                logger.error(f"InitiativeEngine: {detector.__name__} failed: {e}")

        # Deduplicate by title
        seen_titles = set()
        unique = []
        for init in all_initiatives:
            if init.title not in seen_titles:
                seen_titles.add(init.title)
                unique.append(init)

        # Store in memory
        for init in unique:
            await self.memory.put("knowledge", {
                "type": "initiative",
                **init.to_dict(),
            })

        self._initiatives.extend(unique)
        logger.info(f"InitiativeEngine: scan #{self._scan_count} complete — {len(unique)} new initiative(s)")

        # Publish event
        if self.bus and unique:
            await self.bus.publish(
                "initiative.detected",
                {"count": len(unique), "types": [i.type.value for i in unique]},
                source="initiative_engine",
            )

        # Optionally auto-create missions
        if self.auto_create and self.cos:
            for init in unique:
                if init.priority in (InitiativePriority.HIGH, InitiativePriority.CRITICAL):
                    if init.suggested_mission:
                        try:
                            await self.cos.chat(init.suggested_mission)
                            init.auto_created_mission = True
                            logger.info(f"InitiativeEngine: auto-created mission for '{init.title}'")
                        except Exception as e:
                            logger.warning(f"InitiativeEngine: auto-create failed: {e}")

        return unique

    def get_pending_initiatives(self) -> list[Initiative]:
        """Return initiatives that haven't been acted on yet."""
        return [i for i in self._initiatives if not i.auto_created_mission]

    def summary(self) -> str:
        """Human-readable summary for the Chief Of Staff."""
        if not self._initiatives:
            return "No initiatives detected."
        lines = [f"Initiative Engine — {len(self._initiatives)} initiative(s) detected:"]
        for init in self._initiatives[-10:]:  # last 10
            icon = {
                InitiativeType.OPPORTUNITY: "💡",
                InitiativeType.ANOMALY: "⚠️",
                InitiativeType.UPDATE: "🔄",
                InitiativeType.RISK: "🚨",
                InitiativeType.IMPROVEMENT: "🔧",
            }.get(init.type, "•")
            lines.append(f"  {icon} [{init.priority.value}] {init.title}")
        return "\n".join(lines)

    # ── Detectors ───────────────────────────────────────────────────────────

    async def _detect_stale_missions(self) -> list[Initiative]:
        """Detect missions stuck in 'running' status for too long."""
        initiatives = []
        try:
            tasks = await self.memory.query("tasks")
            now = datetime.utcnow()
            for t in tasks:
                status = t.data.get("status", "")
                if status == "running":
                    created = t.data.get("created_at", "")
                    if created:
                        try:
                            created_dt = datetime.fromisoformat(created.replace("Z", ""))
                            age_minutes = (now - created_dt).total_seconds() / 60
                            if age_minutes > 5:  # stuck for > 5 min
                                initiatives.append(Initiative(
                                    id=f"stale-{t.id[:8]}",
                                    type=InitiativeType.ANOMALY,
                                    priority=InitiativePriority.HIGH,
                                    title=f"Mission stuck in 'running' for {int(age_minutes)}min",
                                    description=f"Mission {t.id[:8]} has been running for {int(age_minutes)} minutes. Objective: {t.data.get('objective', '?')[:80]}",
                                    suggested_mission=f"Check the status of mission {t.id[:8]} and cancel it if it's stuck.",
                                    source="stale_mission_detector",
                                    detected_at=now.isoformat(),
                                    metadata={"mission_id": t.id, "age_minutes": int(age_minutes)},
                                ))
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"stale_mission_detector: {e}")
        return initiatives

    async def _detect_failed_patterns(self) -> list[Initiative]:
        """Detect recurring failure patterns across missions."""
        initiatives = []
        try:
            tasks = await self.memory.query("tasks")
            failed = [t for t in tasks if t.data.get("status") == "failed"]
            if len(failed) >= 3:
                # Check if same capability keeps failing
                cap_counts: dict[str, int] = {}
                for t in failed:
                    plan = t.data.get("plan", [])
                    for task in plan:
                        cap = task.get("capability", "unknown")
                        cap_counts[cap] = cap_counts.get(cap, 0) + 1

                for cap, count in cap_counts.items():
                    if count >= 3:
                        initiatives.append(Initiative(
                            id=f"fail-pattern-{cap}",
                            type=InitiativeType.RISK,
                            priority=InitiativePriority.HIGH,
                            title=f"Repeated failures with capability '{cap}' ({count} times)",
                            description=f"The capability '{cap}' has failed in {count} missions. This may indicate a plugin issue.",
                            suggested_mission=f"Investigate why the {cap} capability keeps failing. Check the plugin health and configuration.",
                            source="failed_pattern_detector",
                            detected_at=datetime.utcnow().isoformat(),
                            metadata={"capability": cap, "failure_count": count},
                        ))
        except Exception as e:
            logger.debug(f"failed_pattern_detector: {e}")
        return initiatives

    async def _detect_user_habits(self) -> list[Initiative]:
        """Infer user habits from conversation patterns."""
        initiatives = []
        try:
            conversations = await self.memory.query("conversations")
            if len(conversations) < 10:
                return []

            # Count user messages by time of day (heuristic)
            user_msgs = [c for c in conversations if c.data.get("role") == "user"]
            if len(user_msgs) < 5:
                return []

            # Detect language preference
            french_count = sum(1 for c in user_msgs if any(w in c.data.get("content", "").lower() for w in ["bonjour", "salut", "merci", "crée", "vérifie", "analyse"]))
            if french_count > len(user_msgs) * 0.3:
                # Check if we already have this preference
                prefs = await self.memory.query("preferences", key="language")
                if not prefs:
                    initiatives.append(Initiative(
                        id="habit-language-fr",
                        type=InitiativeType.IMPROVEMENT,
                        priority=InitiativePriority.LOW,
                        title="User prefers French — consider setting language preference",
                        description=f"Detected {french_count} French messages out of {len(user_msgs)}. Setting language=fr would improve responses.",
                        suggested_mission="",  # just a suggestion, not a mission
                        source="user_habit_detector",
                        detected_at=datetime.utcnow().isoformat(),
                        metadata={"french_ratio": french_count / len(user_msgs)},
                    ))
        except Exception as e:
            logger.debug(f"user_habit_detector: {e}")
        return initiatives

    async def _detect_knowledge_gaps(self) -> list[Initiative]:
        """Find entities in memory with stale or missing data."""
        initiatives = []
        try:
            # Check if user has any 'servers' or 'projects' registered
            servers = await self.memory.query("servers")
            projects = await self.memory.query("projects")

            if not servers and not projects:
                # User has been talking but hasn't registered any servers/projects
                conversations = await self.memory.query("conversations")
                if len(conversations) > 5:
                    initiatives.append(Initiative(
                        id="knowledge-gap-no-infra",
                        type=InitiativeType.IMPROVEMENT,
                        priority=InitiativePriority.LOW,
                        title="No servers or projects registered — ALTEREGO can't proactively help",
                        description="You've had several conversations but haven't registered any servers or projects. ALTEREGO could monitor them proactively if you did.",
                        suggested_mission="",
                        source="knowledge_gap_detector",
                        detected_at=datetime.utcnow().isoformat(),
                    ))
        except Exception as e:
            logger.debug(f"knowledge_gap_detector: {e}")
        return initiatives

    async def _detect_memory_growth(self) -> list[Initiative]:
        """Track memory growth — alert if growing too fast (possible leak)."""
        initiatives = []
        try:
            all_records = await self.memory.query("tasks")
            all_convs = await self.memory.query("conversations")
            total = len(all_records) + len(all_convs)

            if total > 10000:
                initiatives.append(Initiative(
                    id="memory-growth-large",
                    type=InitiativeType.ANOMALY,
                    priority=InitiativePriority.MEDIUM,
                    title=f"Memory growing large ({total} records) — consider cleanup",
                    description=f"Memory contains {total} records. Consider archiving old conversations or completed missions.",
                    suggested_mission="Archive old conversations and completed missions to keep memory lean.",
                    source="memory_growth_detector",
                    detected_at=datetime.utcnow().isoformat(),
                    metadata={"total_records": total},
                ))
        except Exception as e:
            logger.debug(f"memory_growth_detector: {e}")
        return initiatives
