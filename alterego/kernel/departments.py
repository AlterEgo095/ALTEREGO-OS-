"""ALTEREGO OS — Departments (as config, not code).

A department is a YAML file declaring:
  - name
  - description
  - capabilities it uses
  - events it subscribes to
  - events it produces
  - agent roles (for CrewAI integration, V2)

Engineering is just one department among many. The Kernel does not
treat it specially — it's a config like any other.

Example department YAML (departments/engineering.yaml):
    name: engineering
    description: Software engineering operations
    capabilities: [github, docker, filesystem, llm.chat]
    subscribes: [mission.created, build.failed]
    publishes: [pr.created, build.passed]
    roles:
      - architect
      - coder
      - reviewer
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, Field


class DepartmentSpec(BaseModel):
    """A department declared in YAML."""
    name: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    subscribes: list[str] = Field(default_factory=list)
    publishes: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)


class DepartmentLoader:
    """Loads department YAML files from a directory.

    Default departments (V1):
      - engineering.yaml
      - research.yaml
      - infrastructure.yaml
      - personal.yaml

    Adding a new department = creating a new YAML file. No code change.
    """

    def __init__(self, departments_dir: Path) -> None:
        self.dir = departments_dir
        self._departments: dict[str, DepartmentSpec] = {}

    def load_all(self) -> list[DepartmentSpec]:
        """Load all department YAML files from the directory."""
        if not self.dir.exists():
            logger.warning(f"DepartmentLoader: directory {self.dir} does not exist")
            return []

        loaded = []
        for yaml_file in sorted(self.dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text()) or {}
                spec = DepartmentSpec(**data)
                self._departments[spec.name] = spec
                loaded.append(spec)
                logger.info(f"DepartmentLoader: loaded '{spec.name}' from {yaml_file.name}")
            except Exception as e:
                logger.error(f"DepartmentLoader: failed to load {yaml_file}: {e}")
        return loaded

    def get(self, name: str) -> DepartmentSpec | None:
        return self._departments.get(name)

    def list(self) -> list[DepartmentSpec]:
        return list(self._departments.values())

    def find_for_capability(self, capability: str) -> list[DepartmentSpec]:
        """Find all departments that use a given capability."""
        return [d for d in self._departments.values() if capability in d.capabilities]

    def describe(self) -> str:
        """Human-readable description for the LLM planner."""
        if not self._departments:
            return "(no departments loaded)"
        lines = []
        for d in self._departments.values():
            caps = ", ".join(d.capabilities) if d.capabilities else "—"
            lines.append(f"  - {d.name}: {d.description} (capabilities: {caps})")
        return "\n".join(lines)
