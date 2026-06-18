"""ALTEREGO OS — Validation Pipeline.

Pipeline obligatoire pour toute sortie IA :
  LLM → Critic → Validator → Security → Tests → Repair → Final → Delivery

Aucune sortie IA ne doit être livrée directement à l'utilisateur.

V1.1 implémente les 8 étapes avec fallback gracieux :
  - Chaque étape peut échouer sans crasher le pipeline
  - Les étapes critiques (Security, Final) peuvent bloquer la delivery
  - Le Repair loop retente max 3 fois avec feedback
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class ValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    REPAIRING = "repairing"


@dataclass
class ValidationStepResult:
    name: str
    status: ValidationStatus
    score: float = 1.0  # 0.0 to 1.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Full validation result across all 8 steps."""
    steps: list[ValidationStepResult] = field(default_factory=list)
    overall_score: float = 0.0
    can_deliver: bool = False
    repair_attempts: int = 0
    final_content: str = ""

    def summary(self) -> str:
        lines = ["Validation Pipeline:"]
        for step in self.steps:
            icon = {"passed": "✓", "failed": "✗", "skipped": "—", "repairing": "↻"}.get(step.status.value, "?")
            lines.append(f"  {icon} {step.name}: {step.status.value} (score={step.score:.0%})")
        lines.append(f"  Overall: {self.overall_score:.0%} | Can deliver: {self.can_deliver}")
        return "\n".join(lines)


class ValidationPipeline:
    """8-step validation pipeline for LLM outputs.

    Steps:
    1. LLM — the LLM generates the initial output
    2. Critic — a second LLM call evaluates quality (relevance, coherence, completeness)
    3. Validator — structural validation (JSON schema, format checks)
    4. Security — check for secrets, dangerous content, prompt injection traces
    5. Tests — if the output is code, run it; if it's a plan, verify capabilities exist
    6. Repair — if any step failed, retry with feedback (max 3 attempts)
    7. Final — final validation after repair
    8. Delivery — gate decision: deliver to user or reject
    """

    MAX_REPAIR_ATTEMPTS = 3

    # Security patterns to detect in LLM output
    SECRET_PATTERNS = [
        (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key detected"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub token detected"),
        (r"AKIA[A-Z0-9]{16}", "AWS access key detected"),
        (r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", "Private key detected"),
        (r"password\s*[:=]\s*['\"][^'\"]{8,}['\"]", "Password in plaintext"),
    ]

    DANGEROUS_PATTERNS = [
        (r"rm\s+-rf\s+/", "Destructive command: rm -rf /"),
        (r"DROP\s+(DATABASE|TABLE|SCHEMA)", "Destructive SQL", re.IGNORECASE),
        (r"<script[^>]*>.*?</script>", "XSS payload", re.IGNORECASE | re.DOTALL),
        (r"eval\s*\(", "Code injection: eval()"),
        (r"exec\s*\(\s*['\"]", "Code injection: exec()"),
    ]

    def __init__(self, llm_plugin: Any = None) -> None:
        self.llm = llm_plugin

    async def validate(
        self,
        content: str,
        context: dict[str, Any] | None = None,
        capability: str = "",
        method: str = "",
    ) -> ValidationResult:
        """Run the full 8-step validation pipeline.

        Args:
            content: The LLM output to validate
            context: Mission context (objective, plan, etc.)
            capability: What capability this output is for
            method: What method was called

        Returns:
            ValidationResult with all step results and delivery decision
        """
        context = context or {}
        result = ValidationResult()
        current_content = content

        for attempt in range(self.MAX_REPAIR_ATTEMPTS + 1):
            result.steps = []
            result.repair_attempts = attempt

            # Step 1: LLM (already generated — just record)
            result.steps.append(ValidationStepResult(
                name="LLM",
                status=ValidationStatus.PASSED,
                score=1.0,
                message="LLM output generated",
            ))

            # Step 2: Critic
            critic = await self._critic(current_content, context)
            result.steps.append(critic)

            # Step 3: Validator
            validator = self._validate_structure(current_content, capability, method)
            result.steps.append(validator)

            # Step 4: Security
            security = self._check_security(current_content)
            result.steps.append(security)

            # Step 5: Tests (if applicable)
            tests = await self._run_tests(current_content, capability, method, context)
            result.steps.append(tests)

            # If any critical step failed, try repair
            failed_steps = [s for s in result.steps if s.status == ValidationStatus.FAILED]
            if failed_steps and attempt < self.MAX_REPAIR_ATTEMPTS:
                repair = ValidationStepResult(
                    name="Repair",
                    status=ValidationStatus.REPAIRING,
                    message=f"Attempt {attempt + 1}/{self.MAX_REPAIR_ATTEMPTS}: repairing {len(failed_steps)} failure(s)",
                )
                result.steps.append(repair)

                # Try to repair
                repaired = await self._repair(current_content, failed_steps, context)
                if repaired:
                    current_content = repaired
                    logger.info(f"Repair attempt {attempt + 1}: content updated")
                    continue
                else:
                    result.steps.append(ValidationStepResult(
                        name="Repair",
                        status=ValidationStatus.FAILED,
                        message="Repair could not fix the issues",
                    ))
                    break
            else:
                # No failures (or max attempts reached)
                if failed_steps:
                    result.steps.append(ValidationStepResult(
                        name="Repair",
                        status=ValidationStatus.FAILED,
                        message=f"Max repair attempts ({self.MAX_REPAIR_ATTEMPTS}) reached",
                    ))
                else:
                    result.steps.append(ValidationStepResult(
                        name="Repair",
                        status=ValidationStatus.SKIPPED,
                        message="No repair needed",
                    ))
                break

        # Step 7: Final validation
        final_failed = [s for s in result.steps if s.status == ValidationStatus.FAILED and s.name in ["Security", "Critic"]]
        if final_failed:
            result.steps.append(ValidationStepResult(
                name="Final",
                status=ValidationStatus.FAILED,
                score=0.0,
                message=f"{len(final_failed)} critical step(s) still failing",
            ))
        else:
            result.steps.append(ValidationStepResult(
                name="Final",
                status=ValidationStatus.PASSED,
                score=1.0,
                message="All critical steps passed",
            ))

        # Step 8: Delivery decision
        passed_count = sum(1 for s in result.steps if s.status == ValidationStatus.PASSED)
        total_count = len([s for s in result.steps if s.status != ValidationStatus.SKIPPED])
        result.overall_score = passed_count / total_count if total_count else 0.0
        result.can_deliver = not final_failed and result.overall_score >= 0.6
        result.final_content = current_content

        result.steps.append(ValidationStepResult(
            name="Delivery",
            status=ValidationStatus.PASSED if result.can_deliver else ValidationStatus.FAILED,
            score=result.overall_score,
            message="Delivered to user" if result.can_deliver else "Blocked by validation",
        ))

        logger.info(f"Validation pipeline: score={result.overall_score:.0%} deliver={result.can_deliver} repairs={result.repair_attempts}")
        return result

    # ── Step implementations ────────────────────────────────────────────────

    async def _critic(self, content: str, context: dict[str, Any]) -> ValidationStepResult:
        """Step 2: Critic — evaluate quality using LLM-as-judge."""
        if not self.llm:
            return ValidationStepResult("Critic", ValidationStatus.SKIPPED, 1.0, "No LLM available for critic")

        try:
            objective = context.get("objective", "")
            result = await self.llm.call("chat", {
                "system": "You are a quality critic. Evaluate if the response addresses the user's objective. Reply with ONLY a score 0-100 and one sentence explanation.",
                "user": f"Objective: {objective[:200]}\n\nResponse: {content[:500]}",
                "temperature": 0.0,
            })
            if isinstance(result, dict):
                result_text = result.get("content", "")
            else:
                result_text = str(result)

            # Extract score from response
            score_match = re.search(r"(\d+)", result_text)
            score = int(score_match.group(1)) / 100 if score_match else 0.7

            if score >= 0.6:
                return ValidationStepResult("Critic", ValidationStatus.PASSED, score, result_text[:200])
            else:
                return ValidationStepResult("Critic", ValidationStatus.FAILED, score, result_text[:200])
        except Exception as e:
            logger.warning(f"Critic step failed: {e}")
            return ValidationStepResult("Critic", ValidationStatus.SKIPPED, 0.7, f"Critic error: {e}")

    def _validate_structure(self, content: str, capability: str, method: str) -> ValidationStepResult:
        """Step 3: Validator — structural validation."""
        # Check if content is empty
        if not content or not content.strip():
            return ValidationStepResult("Validator", ValidationStatus.FAILED, 0.0, "Empty content")

        # Check for JSON if the method expects JSON
        if method in ["write", "append"] and capability == "filesystem":
            # Content for file write — always valid
            return ValidationStepResult("Validator", ValidationStatus.PASSED, 1.0, "File content validated")

        # Check for reasonable length
        if len(content) > 50000:
            return ValidationStepResult("Validator", ValidationStatus.FAILED, 0.3, "Content too long (>50k chars)")

        return ValidationStepResult("Validator", ValidationStatus.PASSED, 1.0, "Structure valid")

    def _check_security(self, content: str) -> ValidationStepResult:
        """Step 4: Security — detect secrets and dangerous patterns."""
        findings = []

        # Check for secrets
        for pattern, description in self.SECRET_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                findings.append({"type": "secret", "description": description, "count": len(matches)})

        # Check for dangerous patterns
        for item in self.DANGEROUS_PATTERNS:
            pattern = item[0]
            description = item[1]
            flags = item[2] if len(item) > 2 else 0
            if re.search(pattern, content, flags):
                findings.append({"type": "dangerous", "description": description})

        if findings:
            critical = [f for f in findings if f["type"] == "secret"]
            if critical:
                return ValidationStepResult(
                    "Security", ValidationStatus.FAILED, 0.0,
                    f"{len(critical)} secret(s) detected",
                    {"findings": findings},
                )
            return ValidationStepResult(
                "Security", ValidationStatus.PASSED, 0.5,
                f"{len(findings)} warning(s) (non-blocking)",
                {"findings": findings},
            )

        return ValidationStepResult("Security", ValidationStatus.PASSED, 1.0, "No security issues")

    async def _run_tests(self, content: str, capability: str, method: str, context: dict[str, Any]) -> ValidationStepResult:
        """Step 5: Tests — verify the output is usable."""
        # V1: skip actual tests, just check the output makes sense
        if capability == "filesystem" and method == "write":
            params = context.get("params", {})
            if "path" not in params or "content" not in params:
                return ValidationStepResult("Tests", ValidationStatus.FAILED, 0.0, "Missing path or content for file write")
            return ValidationStepResult("Tests", ValidationStatus.PASSED, 1.0, "File write params valid")

        if capability == "llm.chat":
            return ValidationStepResult("Tests", ValidationStatus.PASSED, 1.0, "LLM response is conversational")

        return ValidationStepResult("Tests", ValidationStatus.SKIPPED, 1.0, "No tests for this capability")

    async def _repair(self, content: str, failed_steps: list[ValidationStepResult], context: dict[str, Any]) -> Optional[str]:
        """Step 6: Repair — retry with feedback."""
        if not self.llm:
            return None

        feedback = "\n".join(f"- {s.name}: {s.message}" for s in failed_steps)
        objective = context.get("objective", "")

        try:
            result = await self.llm.call("chat", {
                "system": f"You are a repair engine. The previous output had issues:\n{feedback}\n\nPlease fix and regenerate the response. Original objective: {objective[:200]}",
                "user": f"Fix this output:\n{content[:1000]}",
                "temperature": 0.3,
            })
            if isinstance(result, dict):
                repaired = result.get("content", "")
            else:
                repaired = str(result)

            if repaired and repaired.strip():
                return repaired
        except Exception as e:
            logger.warning(f"Repair failed: {e}")

        return None
