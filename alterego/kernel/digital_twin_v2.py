"""ALTEREGO OS V2.1 — Digital Twin V2.

Représentation numérique complète de l'utilisateur.

Le Digital Twin V2 enrichit le V1 avec un graphe de connaissances
liant tous les objets de la vie numérique de l'utilisateur :

  Identity → Companies → Projects → Repositories → Servers
           → Applications → Documents → Clients → Goals
           → Habits → Calendar → Skills → Preferences → History
           → Roadmaps → Decisions

Chaque objet peut être relié à d'autres (un projet appartient à une
entreprise, un serveur héberge des applications, etc.)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from loguru import logger


class DigitalTwinV2:
    """Digital Twin with knowledge graph capabilities.

    Uses Memory as storage. Each entity type is a key in the 'knowledge'
    entity store, with a 'twin_type' field for filtering.

    Relations are stored as separate records:
        {"type": "relation", "from": "project:alterego", "to": "company:zai", "relation": "belongs_to"}
    """

    TWIN_TYPES = [
        "identity", "company", "project", "repository", "server",
        "application", "document", "client", "goal", "habit",
        "calendar_event", "skill", "preference", "history",
        "roadmap", "decision", "relation",
    ]

    def __init__(self, memory: Any, user_id: str = "default") -> None:
        self.memory = memory
        self.user_id = user_id

    # ── Identity ────────────────────────────────────────────────────────────

    async def set_identity(self, name: str, **details: Any) -> str:
        """Set or update the user's identity."""
        existing = await self.memory.query("knowledge")
        old = [r for r in existing if r.data.get("twin_type") == "identity"]
        data = {
            "twin_type": "identity",
            "user_id": self.user_id,
            "name": name,
            "updated_at": datetime.utcnow().isoformat(),
            **details,
        }
        if old:
            await self.memory.update("knowledge", old[0].id, data)
            return old[0].id
        return await self.memory.put("knowledge", data)

    async def get_identity(self) -> dict[str, Any]:
        records = await self.memory.query("knowledge")
        for r in records:
            if r.data.get("twin_type") == "identity":
                return r.data
        return {}

    # ── Generic entity management ───────────────────────────────────────────

    async def add_entity(self, twin_type: str, name: str, **details: Any) -> str:
        """Add any type of entity to the twin."""
        if twin_type not in self.TWIN_TYPES:
            raise ValueError(f"Unknown twin_type '{twin_type}'. Allowed: {self.TWIN_TYPES}")
        record_id = await self.memory.put("knowledge", {
            "twin_type": twin_type,
            "user_id": self.user_id,
            "name": name,
            "created_at": datetime.utcnow().isoformat(),
            **details,
        })
        logger.info(f"DigitalTwinV2: added {twin_type} '{name}'")
        return record_id

    async def get_entities(self, twin_type: str) -> list[dict[str, Any]]:
        """Get all entities of a given type."""
        records = await self.memory.query("knowledge")
        return [r.data for r in records if r.data.get("twin_type") == twin_type]

    async def find_entity(self, twin_type: str, name: str) -> Optional[dict[str, Any]]:
        """Find a specific entity by type and name."""
        entities = await self.get_entities(twin_type)
        for e in entities:
            if e.get("name", "").lower() == name.lower():
                return e
        return None

    async def update_entity(self, twin_type: str, name: str, **updates: Any) -> bool:
        """Update an entity by type and name."""
        records = await self.memory.query("knowledge")
        for r in records:
            if r.data.get("twin_type") == twin_type and r.data.get("name", "").lower() == name.lower():
                merged = {**r.data, **updates, "updated_at": datetime.utcnow().isoformat()}
                await self.memory.update("knowledge", r.id, merged)
                return True
        return False

    # ── Relations (knowledge graph) ─────────────────────────────────────────

    async def add_relation(self, from_entity: str, to_entity: str, relation: str, **details: Any) -> str:
        """Create a relation between two entities.

        Args:
            from_entity: "type:name" (e.g. "project:alterego")
            to_entity: "type:name" (e.g. "company:zai")
            relation: "belongs_to", "hosted_on", "depends_on", "created_by", etc.
        """
        return await self.memory.put("knowledge", {
            "twin_type": "relation",
            "from": from_entity,
            "to": to_entity,
            "relation": relation,
            "created_at": datetime.utcnow().isoformat(),
            **details,
        })

    async def get_relations(self, entity: str | None = None, relation: str | None = None) -> list[dict[str, Any]]:
        """Get relations, optionally filtered by entity or relation type."""
        records = await self.memory.query("knowledge")
        results = []
        for r in records:
            if r.data.get("twin_type") != "relation":
                continue
            if entity and r.data.get("from") != entity and r.data.get("to") != entity:
                continue
            if relation and r.data.get("relation") != relation:
                continue
            results.append(r.data)
        return results

    async def get_related(self, entity: str, direction: str = "both") -> list[dict[str, Any]]:
        """Get all entities related to a given entity.

        Args:
            entity: "type:name"
            direction: "outgoing" (from entity), "incoming" (to entity), "both"
        """
        records = await self.memory.query("knowledge")
        related = []
        for r in records:
            if r.data.get("twin_type") != "relation":
                continue
            if direction in ("outgoing", "both") and r.data.get("from") == entity:
                related.append({"direction": "outgoing", "to": r.data.get("to"), "relation": r.data.get("relation")})
            if direction in ("incoming", "both") and r.data.get("to") == entity:
                related.append({"direction": "incoming", "from": r.data.get("from"), "relation": r.data.get("relation")})
        return related

    # ── Convenience methods ─────────────────────────────────────────────────

    async def add_company(self, name: str, **details: Any) -> str:
        return await self.add_entity("company", name, **details)

    async def add_project(self, name: str, company: str = "", **details: Any) -> str:
        rid = await self.add_entity("project", name, **details)
        if company:
            await self.add_relation(f"project:{name}", f"company:{company}", "belongs_to")
        return rid

    async def add_repository(self, name: str, url: str, project: str = "", **details: Any) -> str:
        rid = await self.add_entity("repository", name, url=url, **details)
        if project:
            await self.add_relation(f"repository:{name}", f"project:{project}", "belongs_to")
        return rid

    async def add_server(self, name: str, host: str, **details: Any) -> str:
        return await self.add_entity("server", name, host=host, **details)

    async def add_application(self, name: str, server: str = "", **details: Any) -> str:
        rid = await self.add_entity("application", name, **details)
        if server:
            await self.add_relation(f"application:{name}", f"server:{server}", "hosted_on")
        return rid

    async def add_client(self, name: str, company: str = "", **details: Any) -> str:
        return await self.add_entity("client", name, **details)

    async def add_decision(self, title: str, description: str = "", **details: Any) -> str:
        return await self.add_entity("decision", title, description=description, **details)

    async def add_skill(self, name: str, level: int = 3, **details: Any) -> str:
        return await self.add_entity("skill", name, level=level, **details)

    async def add_roadmap(self, name: str, **details: Any) -> str:
        return await self.add_entity("roadmap", name, **details)

    async def add_calendar_event(self, title: str, date: str, **details: Any) -> str:
        return await self.add_entity("calendar_event", title, date=date, **details)

    async def add_habit(self, name: str, **details: Any) -> str:
        return await self.add_entity("habit", name, **details)

    # ── Full profile ────────────────────────────────────────────────────────

    async def get_full_profile(self) -> dict[str, Any]:
        """Get the complete digital twin — all entities and relations."""
        profile = {"user_id": self.user_id, "generated_at": datetime.utcnow().isoformat()}

        # Identity
        profile["identity"] = await self.get_identity()

        # All entity types
        for twin_type in self.TWIN_TYPES:
            if twin_type in ("identity", "relation"):
                continue
            entities = await self.get_entities(twin_type)
            if entities:
                profile[twin_type + "s"] = entities

        # Relations
        relations = await self.get_relations()
        if relations:
            profile["relations"] = relations
            profile["relations_count"] = len(relations)

        # Stats
        total_entities = sum(len(v) for k, v in profile.items() if isinstance(v, list) and k != "relations")
        profile["total_entities"] = total_entities
        profile["total_relations"] = len(relations)

        return profile

    async def describe(self) -> str:
        """Human-readable description of the complete twin."""
        profile = await self.get_full_profile()
        identity = profile.get("identity", {})
        name = identity.get("name", self.user_id)

        lines = [f"🧠 Digital Twin V2 — {name}", ""]

        if identity:
            for k, v in identity.items():
                if k not in ("twin_type", "user_id", "updated_at"):
                    lines.append(f"  {k}: {v}")

        for twin_type in self.TWIN_TYPES:
            if twin_type in ("identity", "relation"):
                continue
            key = twin_type + "s"
            items = profile.get(key, [])
            if items:
                lines.append(f"\n── {twin_type.title()}s ({len(items)}) ──")
                for item in items[:5]:
                    lines.append(f"  • {item.get('name', '?')}")

        relations = profile.get("relations", [])
        if relations:
            lines.append(f"\n── Relations ({len(relations)}) ──")
            for r in relations[:5]:
                lines.append(f"  {r.get('from', '?')} →[{r.get('relation', '?')}]→ {r.get('to', '?')}")

        lines.append(f"\n  Total: {profile.get('total_entities', 0)} entities, {profile.get('total_relations', 0)} relations")
        return "\n".join(lines)
