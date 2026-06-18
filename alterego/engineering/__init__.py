"""ALTEREGO OS — Software Engineering Department (Phase 3B).

Safe GitHub workflow with MANDATORY human validation:

    Clone → New Branch → Analyze → Fix → Test → Report → Diff
        → Human Approval Gate
            → YES: Commit → Create PR → Notify
            → NO:  Cleanup branch → No changes

The human ALWAYS has the final say. No automatic commits to main.
No automatic PRs. The gate is blocking and cannot be bypassed.

This module is a department — it uses the Kernel's plugins (github,
filesystem, llm.chat) and respects the PolicyEngine (github.clone=ALLOW,
github.create_pull_request=REQUIRE_APPROVAL).
"""
from __future__ import annotations

import asyncio
import difflib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class ApprovalResult(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class EngineeringReport:
    """Structured report produced by the engineering pipeline."""
    repo: str = ""
    branch: str = ""
    clone_path: str = ""
    files_analyzed: int = 0
    issues_found: list[dict] = field(default_factory=list)
    fixes_proposed: list[dict] = field(default_factory=list)
    tests_run: bool = False
    tests_passed: bool = False
    test_output: str = ""
    diff: str = ""
    files_changed: list[str] = field(default_factory=list)
    approval: ApprovalResult | None = None
    pr_url: str = ""
    pr_number: int = 0
    error: str = ""

    def summary(self) -> str:
        lines = [
            f"Repository: {self.repo}",
            f"Branch: {self.branch}",
            f"Files analyzed: {self.files_analyzed}",
            f"Issues found: {len(self.issues_found)}",
            f"Fixes proposed: {len(self.fixes_proposed)}",
            f"Tests run: {self.tests_run} (passed: {self.tests_passed})",
            f"Files changed: {len(self.files_changed)}",
            f"Approval: {self.approval.value if self.approval else 'pending'}",
        ]
        if self.pr_url:
            lines.append(f"PR: {self.pr_url}")
        if self.error:
            lines.append(f"Error: {self.error}")
        return "\n".join(lines)


class HumanApprovalGate:
    """Blocking gate that requires human approval before commit/PR.

    CANNOT be bypassed. The engineering pipeline stops here until
    the human explicitly approves or rejects.

    In interactive mode: prompts via stdin.
    In API mode (future): returns a pending status, waits for external callback.
    """

    def __init__(self, interactive: bool = True) -> None:
        self.interactive = interactive

    async def request_approval(self, report: EngineeringReport) -> ApprovalResult:
        """Request human approval for the proposed changes.

        Shows the diff, the list of files changed, and asks explicitly.
        Returns APPROVED, REJECTED, or TIMEOUT.
        """
        if not self.interactive:
            # Non-interactive mode: always require explicit external approval
            # In V1, this means REJECTED (no auto-approval ever)
            logger.warning("HumanApprovalGate: non-interactive mode — defaulting to REJECTED (no auto-approval)")
            return ApprovalResult.REJECTED

        # Display the proposed changes
        print("\n" + "=" * 70)
        print("🔍 HUMAN APPROVAL GATE — Review required before any commit/PR")
        print("=" * 70)
        print()
        print(f"Repository: {report.repo}")
        print(f"Branch:     {report.branch}")
        print(f"Files changed: {len(report.files_changed)}")
        for f in report.files_changed:
            print(f"  • {f}")
        print()
        print(f"Issues found: {len(report.issues_found)}")
        for issue in report.issues_found[:5]:
            print(f"  ⚠ {issue.get('file', '?')}: {issue.get('description', '?')}")
        print()
        print(f"Fixes proposed: {len(report.fixes_proposed)}")
        for fix in report.fixes_proposed[:5]:
            print(f"  ✓ {fix.get('file', '?')}: {fix.get('description', '?')}")
        print()
        print(f"Tests: {'✓ passed' if report.tests_passed else '✗ failed' if report.tests_run else '— not run'}")
        print()

        # Show diff (truncated if too long)
        if report.diff:
            print("── DIFF (first 2000 chars) ──")
            print(report.diff[:2000])
            if len(report.diff) > 2000:
                print(f"... ({len(report.diff) - 2000} more chars)")
            print()

        print("=" * 70)
        print("⚠ NO CHANGES WILL BE COMMITTED WITHOUT YOUR EXPLICIT APPROVAL.")
        print("⚠ NO PR WILL BE CREATED WITHOUT YOUR EXPLICIT APPROVAL.")
        print("=" * 70)

        # Loop until valid input
        while True:
            try:
                response = input("\nApprove these changes? [yes/no/detail]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n→ No input — rejecting by default.")
                return ApprovalResult.REJECTED

            if response in {"yes", "y", "oui", "o"}:
                print("✓ Approved — proceeding with commit and PR.")
                return ApprovalResult.APPROVED
            elif response in {"no", "n", "non"}:
                print("✗ Rejected — no changes will be committed. Branch will be cleaned up.")
                return ApprovalResult.REJECTED
            elif response in {"detail", "d"}:
                # Show full diff
                print("\n── FULL DIFF ──")
                print(report.diff)
                continue
            else:
                print("Please type 'yes', 'no', or 'detail'.")


class SoftwareEngineeringDepartment:
    """Engineering department — safe code analysis and fix workflow.

    Pipeline:
        1. Clone repo (or use existing clone)
        2. Create new branch (never work on main)
        3. Analyze code for issues
        4. Propose fixes (LLM-generated, applied to working copy)
        5. Run tests (if available)
        6. Generate diff
        7. Human Approval Gate (BLOCKING)
        8. If approved: commit + create PR
        9. If rejected: cleanup, no changes
    """

    BRANCH_PREFIX = "alterego/fix"

    def __init__(
        self,
        llm_plugin: Any = None,
        github_plugin: Any = None,
        filesystem_plugin: Any = None,
        approval_gate: HumanApprovalGate | None = None,
    ) -> None:
        self.llm = llm_plugin
        self.github = github_plugin
        self.fs = filesystem_plugin
        self.gate = approval_gate or HumanApprovalGate(interactive=True)

    async def run(
        self,
        repo: str,
        issue_description: str = "",
        auto_test: bool = True,
        skip_approval: bool = False,
    ) -> EngineeringReport:
        """Run the full engineering pipeline on a repo.

        Args:
            repo: GitHub repo in 'owner/name' format (will be cloned)
            issue_description: What to fix/analyze (natural language)
            auto_test: Run tests if test files are found
            skip_approval: If True, skip the human gate (DANGEROUS — only for testing)

        Returns:
            EngineeringReport with full details
        """
        report = EngineeringReport(repo=repo)
        start = time.perf_counter()

        try:
            # Step 1: Clone
            print(f"\n{'─' * 70}")
            print(f"Step 1/8: Clone {repo}")
            print(f"{'─' * 70}")
            clone_path = await self._clone(repo)
            report.clone_path = clone_path
            print(f"  ✓ Cloned to {clone_path}")

            # Step 2: Create new branch
            print(f"\n{'─' * 70}")
            print(f"Step 2/8: Create new branch")
            print(f"{'─' * 70}")
            branch_name = f"{self.BRANCH_PREFIX}-{int(time.time())}"
            await self._create_branch(clone_path, branch_name)
            report.branch = branch_name
            print(f"  ✓ Branch: {branch_name}")

            # Step 3: Analyze
            print(f"\n{'─' * 70}")
            print(f"Step 3/8: Analyze code")
            print(f"{'─' * 70}")
            issues = await self._analyze(clone_path, issue_description)
            report.issues_found = issues
            report.files_analyzed = len(self._list_python_files(clone_path))
            print(f"  ✓ {report.files_analyzed} files analyzed")
            print(f"  ✓ {len(issues)} issues found")
            for issue in issues[:5]:
                print(f"    ⚠ {issue.get('file')}: {issue.get('description', '')[:80]}")

            # Step 4: Propose fixes
            print(f"\n{'─' * 70}")
            print(f"Step 4/8: Propose fixes")
            print(f"{'─' * 70}")
            fixes = await self._propose_fixes(clone_path, issues, issue_description)
            report.fixes_proposed = fixes
            print(f"  ✓ {len(fixes)} fixes proposed")
            for fix in fixes[:5]:
                print(f"    ✓ {fix.get('file')}: {fix.get('description', '')[:80]}")

            # Step 5: Run tests
            if auto_test:
                print(f"\n{'─' * 70}")
                print(f"Step 5/8: Run tests")
                print(f"{'─' * 70}")
                test_result = await self._run_tests(clone_path)
                report.tests_run = test_result["run"]
                report.tests_passed = test_result["passed"]
                report.test_output = test_result["output"][:2000]
                if test_result["run"]:
                    print(f"  {'✓ Tests passed' if test_result['passed'] else '✗ Tests failed'}")
                else:
                    print(f"  — No tests found or test runner unavailable")

            # Step 6: Generate diff
            print(f"\n{'─' * 70}")
            print(f"Step 6/8: Generate diff")
            print(f"{'─' * 70}")
            diff, changed_files = await self._generate_diff(clone_path)
            report.diff = diff
            report.files_changed = changed_files
            print(f"  ✓ {len(changed_files)} files changed")
            if changed_files:
                print(f"  Diff size: {len(diff)} chars")

            # Step 7: Human Approval Gate
            print(f"\n{'─' * 70}")
            print(f"Step 7/8: Human Approval Gate")
            print(f"{'─' * 70}")

            if skip_approval:
                print("  ⚠ APPROVAL SKIPPED (testing mode) — no commit/PR will be made")
                report.approval = ApprovalResult.REJECTED
            else:
                report.approval = await self.gate.request_approval(report)

            # Step 8: Commit + PR (only if approved)
            print(f"\n{'─' * 70}")
            print(f"Step 8/8: Commit + Pull Request")
            print(f"{'─' * 70}")

            if report.approval == ApprovalResult.APPROVED:
                # Commit
                await self._commit(clone_path, branch_name, issue_description)
                print(f"  ✓ Committed to branch {branch_name}")

                # Create PR
                if self.github:
                    pr_result = await self._create_pr(repo, branch_name, report)
                    report.pr_url = pr_result.get("url", "")
                    report.pr_number = pr_result.get("number", 0)
                    print(f"  ✓ PR created: {report.pr_url}")
                else:
                    print(f"  ⚠ No GitHub plugin — PR not created (commit is local only)")
            else:
                print(f"  ✗ Not approved — no commit, no PR")
                # Cleanup: reset branch changes
                await self._cleanup(clone_path)
                print(f"  ✓ Branch cleaned up — no changes persisted")

            elapsed = time.perf_counter() - start
            print(f"\n{'=' * 70}")
            print(f"Engineering pipeline completed in {elapsed:.1f}s")
            print(f"{'=' * 70}")
            print(report.summary())

        except Exception as e:
            report.error = str(e)
            logger.error(f"Engineering pipeline failed: {e}")
            print(f"\n✗ Pipeline error: {e}")

        return report

    # ── Step implementations ────────────────────────────────────────────────

    async def _clone(self, repo: str) -> str:
        """Clone a repo using git subprocess."""
        tmp = tempfile.mkdtemp(prefix="alterego-eng-")
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", f"https://github.com/{repo}.git", tmp,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed: {stderr.decode()[:200]}")
        return tmp

    async def _create_branch(self, clone_path: str, branch_name: str) -> None:
        """Create a new branch in the cloned repo."""
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", clone_path, "checkout", "-b", branch_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

    def _list_python_files(self, path: str) -> list[Path]:
        """List Python files in a repo (excluding common ignores)."""
        ignore = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build", ".pytest_cache"}
        root = Path(path)
        files = []
        for p in root.rglob("*.py"):
            if any(part in ignore for part in p.relative_to(root).parts):
                continue
            files.append(p)
        return files

    async def _analyze(self, clone_path: str, issue_description: str) -> list[dict]:
        """Analyze code for issues using static heuristics + LLM.

        V1 uses simple heuristics (TODO/FIXME, missing docstrings, bare except).
        V2 will use proper AST analysis + LLM code review.
        """
        issues = []
        py_files = self._list_python_files(clone_path)[:50]  # limit for V1

        for py in py_files:
            try:
                content = py.read_text(errors="ignore")
                rel = str(py.relative_to(clone_path))

                # Check for FIXME
                for i, line in enumerate(content.split("\n"), 1):
                    if "FIXME" in line:
                        issues.append({
                            "file": rel,
                            "line": i,
                            "type": "fixme",
                            "description": f"FIXME marker: {line.strip()[:80]}",
                            "severity": "warning",
                        })

                # Check for bare except
                for i, line in enumerate(content.split("\n"), 1):
                    if line.strip() == "except:":
                        issues.append({
                            "file": rel,
                            "line": i,
                            "type": "bare_except",
                            "description": "Bare except clause — should catch specific exceptions",
                            "severity": "warning",
                        })

                # Check for missing docstrings on public functions
                if "def " in content and '"""' not in content and "'''" not in content:
                    issues.append({
                        "file": rel,
                        "line": 1,
                        "type": "missing_docstring",
                        "description": "File has functions but no docstrings",
                        "severity": "info",
                    })

            except Exception:
                pass

        # If LLM available, ask for additional analysis
        if self.llm and issue_description:
            try:
                # Read first few files for context
                context = ""
                for py in py_files[:3]:
                    context += f"\n--- {py.relative_to(clone_path)} ---\n{py.read_text(errors='ignore')[:500]}\n"

                result = await self.llm.call("chat", {
                    "system": "You are a code analyzer. Identify the top 3 issues in this code. Be concise.",
                    "user": f"Focus: {issue_description}\n\nCode:\n{context[:2000]}",
                })
                if isinstance(result, dict):
                    llm_issues_text = result.get("content", "")
                    if llm_issues_text:
                        issues.append({
                            "file": "(LLM analysis)",
                            "line": 0,
                            "type": "llm_review",
                            "description": llm_issues_text[:300],
                            "severity": "info",
                        })
            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}")

        return issues[:20]  # cap

    async def _propose_fixes(self, clone_path: str, issues: list[dict], issue_description: str) -> list[dict]:
        """Propose fixes for the found issues.

        V1: only fixes bare except clauses (safe, mechanical fix).
        V2 will use LLM to generate patches.
        """
        fixes = []
        root = Path(clone_path)

        for issue in issues:
            if issue["type"] == "bare_except":
                file_path = root / issue["file"]
                try:
                    content = file_path.read_text()
                    lines = content.split("\n")
                    # Replace "except:" with "except Exception:"
                    if issue["line"] - 1 < len(lines):
                        old_line = lines[issue["line"] - 1]
                        new_line = old_line.replace("except:", "except Exception:")
                        lines[issue["line"] - 1] = new_line
                        file_path.write_text("\n".join(lines))
                        fixes.append({
                            "file": issue["file"],
                            "line": issue["line"],
                            "description": "Replaced bare except with except Exception:",
                            "old": old_line.strip(),
                            "new": new_line.strip(),
                        })
                except Exception as e:
                    logger.warning(f"Could not apply fix to {issue['file']}: {e}")

            elif issue["type"] == "fixme" and self.llm:
                # Ask LLM for a fix suggestion (don't apply automatically)
                try:
                    result = await self.llm.call("chat", {
                        "system": "You are a code fixer. Suggest a fix for this issue in one sentence.",
                        "user": f"File: {issue['file']}:{issue['line']}\nIssue: {issue['description']}",
                    })
                    if isinstance(result, dict):
                        suggestion = result.get("content", "")
                        fixes.append({
                            "file": issue["file"],
                            "line": issue["line"],
                            "description": f"LLM suggestion: {suggestion[:100]}",
                            "applied": False,
                        })
                except Exception:
                    pass

        return fixes

    async def _run_tests(self, clone_path: str) -> dict:
        """Run tests if a test runner is available."""
        has_tests = any(
            "test" in str(p.name).lower()
            for p in Path(clone_path).rglob("*.py")
            if ".git" not in str(p)
        )
        if not has_tests:
            return {"run": False, "passed": False, "output": "No test files found"}

        # Try pytest
        proc = await asyncio.create_subprocess_exec(
            "python3", "-m", "pytest", "--tb=short", "-q",
            cwd=clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode() + stderr.decode()
        return {
            "run": True,
            "passed": proc.returncode == 0,
            "output": output,
        }

    async def _generate_diff(self, clone_path: str) -> tuple[str, list[str]]:
        """Generate a git diff of all changes."""
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", clone_path, "diff",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        diff = stdout.decode()

        # Get changed files
        proc2 = await asyncio.create_subprocess_exec(
            "git", "-C", clone_path, "diff", "--name-only",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout2, _ = await proc2.communicate()
        changed = [f.strip() for f in stdout2.decode().split("\n") if f.strip()]

        return diff, changed

    async def _commit(self, clone_path: str, branch_name: str, description: str) -> None:
        """Stage and commit changes to the branch."""
        # git add -A
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", clone_path, "add", "-A",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        # git commit
        msg = f"alterego: {description[:80] or 'automated fix'}\n\nGenerated by ALTEREGO OS Software Engineering Department.\nBranch: {branch_name}"
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", clone_path, "commit", "-m", msg,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

    async def _create_pr(self, repo: str, branch: str, report: EngineeringReport) -> dict:
        """Create a pull request via the GitHub plugin."""
        if not self.github:
            return {}

        title = f"ALTEREGO: {len(report.fixes_proposed)} fix(es) for {report.repo}"
        body = f"""## ALTEREGO OS — Software Engineering Report

**Repository:** {report.repo}
**Branch:** {report.branch}

### Issues found ({len(report.issues_found)})
{chr(10).join(f"- ⚠ {i['file']}:{i.get('line', '?')} — {i['description'][:80]}" for i in report.issues_found[:10])}

### Fixes applied ({len(report.fixes_proposed)})
{chr(10).join(f"- ✓ {f['file']}:{f.get('line', '?')} — {f['description'][:80]}" for f in report.fixes_proposed[:10])}

### Tests
- Run: {report.tests_run}
- Passed: {report.tests_passed}

### Files changed ({len(report.files_changed)})
{chr(10).join(f"- `{f}`" for f in report.files_changed)}

---
🤖 Generated by ALTEREGO OS — Software Engineering Department
⚠ Human-approved: {report.approval.value if report.approval else 'N/A'}
"""
        try:
            result = await self.github.call("create_pull_request", {
                "repo": repo,
                "title": title,
                "head": branch,
                "base": "main",
                "body": body,
            })
            return result
        except Exception as e:
            logger.error(f"PR creation failed: {e}")
            return {"error": str(e)}

    async def _cleanup(self, clone_path: str) -> None:
        """Reset changes on rejected approval."""
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", clone_path, "checkout", "--", ".",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
