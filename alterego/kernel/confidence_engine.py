"""ALTEREGO OS — Confidence Engine.

Produces a confidence score (0-100) for each mission based on:
  - LLM plan validity (was the JSON parseable?)
  - Plan length (very long plans = less confidence)
  - Capability availability (all capabilities available?)
  - Historical success rate (per capability)
  - Policy risk level (high risk = lower confidence)

Decision thresholds:
  - score >= 95 → auto-execute
  - 80 <= score < 95 → recommend validation (execute with notification)
  - score < 80 → require validation (must ask user)
"""
from __future__ import annotations

from typing import Any

from loguru import logger


class ConfidenceEngine:
    """Computes a confidence score for a mission plan.

    The score is a heuristic — not a probability. It reflects how much
    we trust the plan to succeed without causing harm.
    """

    # Weights (sum to 100)
    W_PLAN_VALIDITY = 25       # was the LLM output parseable?
    W_PLAN_LENGTH = 10         # shorter plans = more confidence
    W_CAPABILITY_AVAIL = 25    # are all capabilities available?
    W_HISTORICAL_SUCCESS = 25  # past success rate per capability
    W_POLICY_RISK = 15         # high-risk plans = less confidence

    def __init__(self, plugin_manager: Any, policy_engine: Any, memory: Any) -> None:
        self.pm = plugin_manager
        self.policy = policy_engine
        self.memory = memory
        # Cache for historical success rates (capability → (success, total))
        self._stats_cache: dict[str, tuple[int, int]] = {}
        self._cache_loaded = False

    async def _load_stats(self) -> None:
        """Load historical success rates from memory."""
        if self._cache_loaded:
            return
        try:
            records = await self.memory.query("tasks")
            cap_stats: dict[str, tuple[int, int]] = {}
            for r in records:
                plan = r.data.get("plan", [])
                status = r.data.get("status", "")
                for task in plan:
                    cap = task.get("capability", "unknown")
                    s, t = cap_stats.get(cap, (0, 0))
                    if status == "completed":
                        cap_stats[cap] = (s + 1, t + 1)
                    elif status in {"failed", "running"}:
                        cap_stats[cap] = (s, t + 1)
            self._stats_cache = cap_stats
            self._cache_loaded = True
        except Exception as e:
            logger.warning(f"ConfidenceEngine: could not load stats: {e}")

    async def score(self, plan: list[dict], user_objective: str = "") -> dict[str, Any]:
        """Compute a confidence score for a plan.

        Returns:
            {
                "score": int (0-100),
                "decision": "auto" | "recommend_validation" | "require_validation",
                "factors": {
                    "plan_validity": float,
                    "plan_length": float,
                    "capability_availability": float,
                    "historical_success": float,
                    "policy_risk": float,
                },
                "missing_capabilities": list[str],
                "high_risk_tasks": list[dict],
            }
        """
        await self._load_stats()

        factors = {}
        missing_capabilities = []
        high_risk_tasks = []
        max_risk = "low"

        # 1. Plan validity
        if plan and isinstance(plan, list):
            factors["plan_validity"] = 1.0
        else:
            factors["plan_validity"] = 0.0

        # 2. Plan length (sweet spot = 3-5 tasks)
        n = len(plan)
        if n == 0:
            factors["plan_length"] = 0.0
        elif n <= 5:
            factors["plan_length"] = 1.0
        elif n <= 10:
            factors["plan_length"] = 0.7
        elif n <= 20:
            factors["plan_length"] = 0.4
        else:
            factors["plan_length"] = 0.1

        # 3. Capability availability
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        if plan:
            available = 0
            for task in plan:
                cap = task.get("capability", "")
                method = task.get("method", "")
                plugin = self.pm.best_for(cap)
                if plugin:
                    available += 1
                else:
                    if cap not in missing_capabilities:
                        missing_capabilities.append(cap)
                # Check policy risk
                policy_result = self.policy.evaluate(cap, method, task.get("params", {}))
                risk = policy_result.get("risk", "medium")
                if risk_order.get(risk, 1) > risk_order.get(max_risk, 0):
                    max_risk = risk
                if risk in {"high", "critical"}:
                    high_risk_tasks.append({
                        "step": task.get("step"),
                        "description": task.get("description"),
                        "capability": cap,
                        "method": method,
                        "risk": risk,
                    })
            factors["capability_availability"] = available / len(plan)
        else:
            factors["capability_availability"] = 0.0

        # 4. Historical success
        if plan:
            total_success = 0
            total_count = 0
            for task in plan:
                cap = task.get("capability", "unknown")
                s, t = self._stats_cache.get(cap, (0, 0))
                total_success += s
                total_count += t
            if total_count > 0:
                factors["historical_success"] = total_success / total_count
            else:
                factors["historical_success"] = 0.7  # neutral prior for new capabilities
        else:
            factors["historical_success"] = 0.0

        # 5. Policy risk (lower risk = higher confidence)
        risk_scores = {"low": 1.0, "medium": 0.7, "high": 0.4, "critical": 0.1}
        factors["policy_risk"] = risk_scores.get(max_risk, 0.5)

        # Compute weighted score
        score = (
            factors["plan_validity"] * self.W_PLAN_VALIDITY
            + factors["plan_length"] * self.W_PLAN_LENGTH
            + factors["capability_availability"] * self.W_CAPABILITY_AVAIL
            + factors["historical_success"] * self.W_HISTORICAL_SUCCESS
            + factors["policy_risk"] * self.W_POLICY_RISK
        )
        score = int(round(score))

        # Decision thresholds
        if score >= 95:
            decision = "auto"
        elif score >= 80:
            decision = "recommend_validation"
        else:
            decision = "require_validation"

        logger.info(f"ConfidenceEngine: score={score} decision={decision} (risk={max_risk}, missing={missing_capabilities})")

        return {
            "score": score,
            "decision": decision,
            "factors": {k: round(v, 2) for k, v in factors.items()},
            "missing_capabilities": missing_capabilities,
            "high_risk_tasks": high_risk_tasks,
            "max_risk": max_risk,
        }
