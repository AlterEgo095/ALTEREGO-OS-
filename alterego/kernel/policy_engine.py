"""ALTEREGO OS — Policy Engine.

Decides whether a mission/task can be executed, requires approval, or is denied.

Policies are declarative (YAML) and rule-based:
  - capability allowlist (what the system is allowed to do)
  - action risk levels (low / medium / high / critical)
  - auto-approve threshold (risk < threshold → auto)
  - require-approval threshold (risk >= threshold → ask user)
  - hard denials (e.g. "rm -rf /", "drop database", "send email to all clients")

This is the safety net of the system. The Chief Of Staff NEVER executes
a mission without first asking the Policy Engine.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"          # read-only, no side effects (auto-approve)
    MEDIUM = "medium"    # local writes, reversible (auto-approve with logging)
    HIGH = "high"        # external side effects, may be hard to reverse (require approval)
    CRITICAL = "critical"  # destructive, irreversible (always require approval)


class PolicyDecision(str, Enum):
    ALLOW = "allow"                    # auto-execute
    REQUIRE_APPROVAL = "require_approval"  # ask user first
    DENY = "deny"                      # never execute


class PolicyRule(BaseModel):
    """A single policy rule."""
    name: str
    description: str = ""
    capability: str | None = None  # if set, applies to this capability
    method_pattern: str | None = None  # regex on method name
    risk: RiskLevel
    decision: PolicyDecision
    rationale: str = ""


class PolicyEngine:
    """Evaluates a (capability, method, params) tuple against policies.

    Default policies (overridable via YAML):
      - read-only operations (filesystem.read, github.get_repo_info, etc.) → ALLOW
      - local writes (filesystem.write) → ALLOW with MEDIUM risk
      - external comms (email.send, telegram.send_message) → REQUIRE_APPROVAL
      - destructive ops (filesystem.delete, docker.stop) → REQUIRE_APPROVAL
      - critical ops (docker.delete, ssh.exec with rm -rf) → DENY by default
    """

    DEFAULT_POLICIES = [
        PolicyRule(
            name="read_only_auto_allow",
            description="Read-only operations are auto-approved",
            risk=RiskLevel.LOW,
            decision=PolicyDecision.ALLOW,
            rationale="No side effects, safe to execute",
        ),
        PolicyRule(
            name="filesystem_write_medium",
            capability="filesystem",
            method_pattern="write|append|mkdir",
            risk=RiskLevel.MEDIUM,
            decision=PolicyDecision.ALLOW,
            rationale="Local file writes are reversible",
        ),
        PolicyRule(
            name="filesystem_delete_high",
            capability="filesystem",
            method_pattern="delete|move",
            risk=RiskLevel.HIGH,
            decision=PolicyDecision.REQUIRE_APPROVAL,
            rationale="File deletion may be irreversible",
        ),
        PolicyRule(
            name="github_clone_allow",
            capability="github",
            method_pattern="clone|get_repo_info|list_repos|list_commits",
            risk=RiskLevel.LOW,
            decision=PolicyDecision.ALLOW,
            rationale="Read-only GitHub operations",
        ),
        PolicyRule(
            name="github_write_high",
            capability="github",
            method_pattern="create_issue|create_pull_request|commit",
            risk=RiskLevel.HIGH,
            decision=PolicyDecision.REQUIRE_APPROVAL,
            rationale="GitHub writes have external visibility",
        ),
        PolicyRule(
            name="docker_ps_logs_allow",
            capability="docker",
            method_pattern="ps|logs|stats",
            risk=RiskLevel.LOW,
            decision=PolicyDecision.ALLOW,
            rationale="Read-only Docker operations",
        ),
        PolicyRule(
            name="docker_restart_high",
            capability="docker",
            method_pattern="restart|stop|start",
            risk=RiskLevel.HIGH,
            decision=PolicyDecision.REQUIRE_APPROVAL,
            rationale="Container lifecycle changes affect running services",
        ),
        PolicyRule(
            name="docker_build_exec_high",
            capability="docker",
            method_pattern="build|exec",
            risk=RiskLevel.HIGH,
            decision=PolicyDecision.REQUIRE_APPROVAL,
            rationale="Docker build/exec may have side effects",
        ),
        PolicyRule(
            name="ssh_exec_critical",
            capability="ssh",
            method_pattern="exec",
            risk=RiskLevel.CRITICAL,
            decision=PolicyDecision.REQUIRE_APPROVAL,
            rationale="SSH exec runs arbitrary commands on remote servers",
        ),
        PolicyRule(
            name="browser_allow",
            capability="browser",
            method_pattern=".*",
            risk=RiskLevel.LOW,
            decision=PolicyDecision.ALLOW,
            rationale="Browser automation is sandboxed (Playwright)",
        ),
        PolicyRule(
            name="database_query_allow",
            capability="database.sql",
            method_pattern="query",
            risk=RiskLevel.LOW,
            decision=PolicyDecision.ALLOW,
            rationale="Read-only SQL query",
        ),
        PolicyRule(
            name="database_execute_high",
            capability="database.sql",
            method_pattern="execute|transaction",
            risk=RiskLevel.HIGH,
            decision=PolicyDecision.REQUIRE_APPROVAL,
            rationale="SQL execute may modify data",
        ),
        PolicyRule(
            name="database_nosql_find_allow",
            capability="database.nosql",
            method_pattern="find|find_one|count",
            risk=RiskLevel.LOW,
            decision=PolicyDecision.ALLOW,
            rationale="Read-only Mongo operations",
        ),
        PolicyRule(
            name="database_nosql_modify_high",
            capability="database.nosql",
            method_pattern="insert|update|delete",
            risk=RiskLevel.HIGH,
            decision=PolicyDecision.REQUIRE_APPROVAL,
            rationale="Mongo writes modify data",
        ),
        PolicyRule(
            name="llm_chat_allow",
            capability="llm.chat",
            method_pattern=".*",
            risk=RiskLevel.LOW,
            decision=PolicyDecision.ALLOW,
            rationale="LLM chat is read-only at the system level",
        ),
        PolicyRule(
            name="email_send_high",
            capability="email",
            method_pattern="send",
            risk=RiskLevel.HIGH,
            decision=PolicyDecision.REQUIRE_APPROVAL,
            rationale="Email sends have external recipients",
        ),
        PolicyRule(
            name="telegram_send_high",
            capability="telegram",
            method_pattern="send_.*",
            risk=RiskLevel.HIGH,
            decision=PolicyDecision.REQUIRE_APPROVAL,
            rationale="Telegram messages reach external users",
        ),
    ]

    # Hard denials — these patterns always trigger DENY regardless of capability
    FORBIDDEN_PATTERNS = [
        # Destructive shell patterns
        {"pattern": r"rm\s+-rf\s+/", "reason": "rm -rf / is forbidden"},
        {"pattern": r"mkfs\.", "reason": "Disk formatting is forbidden"},
        {"pattern": r"dd\s+if=/dev/zero\s+of=/dev/", "reason": "Disk wiping is forbidden"},
        # Database destruction
        {"pattern": r"DROP\s+(DATABASE|SCHEMA|TABLE)", "reason": "DROP operations forbidden", "flags": "i"},
        {"pattern": r"TRUNCATE\s+TABLE", "reason": "TRUNCATE forbidden", "flags": "i"},
        # Privilege escalation
        {"pattern": r"sudo\s+rm", "reason": "sudo rm forbidden"},
        {"pattern": r"chmod\s+777\s+/", "reason": "chmod 777 on root forbidden"},
        # Secret exfiltration
        {"pattern": r"curl.*\|\s*sh", "reason": "curl pipe to shell forbidden"},
        {"pattern": r"wget.*\|\s*sh", "reason": "wget pipe to shell forbidden"},
    ]

    def __init__(self, policies_yaml: Path | None = None) -> None:
        self._rules: list[PolicyRule] = list(self.DEFAULT_POLICIES)
        if policies_yaml and policies_yaml.exists():
            self._load_yaml(policies_yaml)

    def _load_yaml(self, path: Path) -> None:
        """Load custom policies from YAML. Overrides defaults with same name."""
        data = yaml.safe_load(path.read_text()) or {}
        custom_rules = data.get("rules", [])
        custom_names = {r["name"] for r in custom_rules}
        # Remove defaults with same name
        self._rules = [r for r in self._rules if r.name not in custom_names]
        # Add custom rules
        for r in custom_rules:
            self._rules.append(PolicyRule(**r))
        logger.info(f"PolicyEngine: loaded {len(custom_rules)} custom policies from {path}")

    def evaluate(self, capability: str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Evaluate a (capability, method, params) tuple against policies.

        Returns:
            {
                "decision": "allow" | "require_approval" | "deny",
                "risk": "low" | "medium" | "high" | "critical",
                "rule": "rule_name",
                "rationale": "human-readable explanation",
                "forbidden_pattern": "if denied by pattern, which one"
            }
        """
        params = params or {}

        # 1. Check forbidden patterns first (always DENY)
        import re
        params_str = str(params)
        for fp in self.FORBIDDEN_PATTERNS:
            flags = re.IGNORECASE if fp.get("flags") == "i" else 0
            if re.search(fp["pattern"], params_str, flags):
                logger.warning(f"PolicyEngine: DENY — forbidden pattern matched: {fp['reason']}")
                return {
                    "decision": PolicyDecision.DENY.value,
                    "risk": RiskLevel.CRITICAL.value,
                    "rule": "forbidden_pattern",
                    "rationale": fp["reason"],
                    "forbidden_pattern": fp["pattern"],
                }

        # 2. Find matching rules — separate specific rules from the catch-all default
        specific_matches = []
        default_match = None
        for rule in self._rules:
            # Skip the catch-all default for now
            if rule.capability is None and rule.method_pattern is None:
                default_match = rule
                continue
            # Check capability match
            if rule.capability and rule.capability != capability:
                continue
            # Check method pattern match
            if rule.method_pattern:
                if not re.search(rule.method_pattern, method):
                    continue
            specific_matches.append(rule)

        # 3. If specific rules matched, use them (highest risk wins)
        if specific_matches:
            specific_matches.sort(key=lambda r: list(RiskLevel).index(r.risk), reverse=True)
            rule = specific_matches[0]
            logger.debug(f"PolicyEngine: ({capability}, {method}) → {rule.decision.value} (risk={rule.risk.value}, rule={rule.name})")
            return {
                "decision": rule.decision.value,
                "risk": rule.risk.value,
                "rule": rule.name,
                "rationale": rule.rationale,
            }

        # 4. If no specific rule matched but there's a catch-all default, use it
        if default_match:
            logger.debug(f"PolicyEngine: ({capability}, {method}) → {default_match.decision.value} (default rule, risk={default_match.risk.value})")
            return {
                "decision": default_match.decision.value,
                "risk": default_match.risk.value,
                "rule": default_match.name,
                "rationale": default_match.rationale,
            }

        # 5. No rule matched at all — safe default: REQUIRE_APPROVAL
        logger.warning(f"PolicyEngine: no rule for ({capability}, {method}) — defaulting to require_approval")
        return {
            "decision": PolicyDecision.REQUIRE_APPROVAL.value,
            "risk": RiskLevel.MEDIUM.value,
            "rule": "default_unknown",
            "rationale": f"No policy defined for ({capability}, {method}) — requiring approval by default",
        }

    def list_rules(self) -> list[dict]:
        return [r.model_dump() for r in self._rules]
