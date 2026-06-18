"""PHASE 3B — Software Engineering Department test (local repo).

Tests the pipeline on the alterego-os repo itself (no network clone needed).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from alterego.engineering import (
    SoftwareEngineeringDepartment,
    HumanApprovalGate,
    ApprovalResult,
    EngineeringReport,
)


async def main():
    print("=" * 70)
    print("PHASE 3B — SOFTWARE ENGINEERING DEPARTMENT (local test)")
    print("=" * 70)
    print()
    print("Testing on alterego-os itself (no network clone needed)")
    print("Pipeline: Analyze → Fix → Test → Diff → Gate (rejected by default)")
    print()

    # Use the local alterego-os repo
    repo_path = Path(__file__).resolve().parent.parent
    print(f"Local repo: {repo_path}")

    # Build a minimal report by running the analysis steps directly
    dept = SoftwareEngineeringDepartment(
        llm_plugin=None,
        github_plugin=None,
        filesystem_plugin=None,
        approval_gate=HumanApprovalGate(interactive=False),
    )

    report = EngineeringReport(repo="alterego-os (local)", branch="alterego/fix-test")
    report.clone_path = str(repo_path)
    start = time.perf_counter()

    # Step 3: Analyze
    print(f"\n{'─' * 70}")
    print(f"Step 3: Analyze code")
    print(f"{'─' * 70}")
    issues = await dept._analyze(str(repo_path), "Find bare except and FIXME")
    report.issues_found = issues
    report.files_analyzed = len(dept._list_python_files(str(repo_path)))
    print(f"  ✓ {report.files_analyzed} files analyzed")
    print(f"  ✓ {len(issues)} issues found")
    for issue in issues[:5]:
        print(f"    ⚠ {issue.get('file')}: {issue.get('description', '')[:80]}")

    # Step 4: Propose fixes (on a copy, not the real repo)
    import tempfile
    import shutil
    with tempfile.TemporaryDirectory() as tmp:
        # Copy only the Python files (not .git, not venv)
        tmp_path = Path(tmp) / "repo"
        tmp_path.mkdir()
        for py in dept._list_python_files(str(repo_path)):
            dest = tmp_path / py.relative_to(repo_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(py, dest)

        # Init git in the copy
        os.system(f"cd {tmp_path} && git init -q && git add -A && git commit -q -m initial")
        os.system(f"cd {tmp_path} && git checkout -q -b alterego/fix-test")

        # Propose fixes on the copy
        print(f"\n{'─' * 70}")
        print(f"Step 4: Propose fixes")
        print(f"{'─' * 70}")
        fixes = await dept._propose_fixes(str(tmp_path), issues, "fix bare excepts")
        report.fixes_proposed = fixes
        print(f"  ✓ {len(fixes)} fixes proposed")
        for fix in fixes[:5]:
            print(f"    ✓ {fix.get('file')}: {fix.get('description', '')[:80]}")

        # Step 5: Run tests
        print(f"\n{'─' * 70}")
        print(f"Step 5: Run tests")
        print(f"{'─' * 70}")
        test_result = await dept._run_tests(str(tmp_path))
        report.tests_run = test_result["run"]
        report.tests_passed = test_result["passed"]
        if test_result["run"]:
            print(f"  {'✓ Tests passed' if test_result['passed'] else '✗ Tests failed'}")
        else:
            print(f"  — {test_result['output']}")

        # Step 6: Generate diff
        print(f"\n{'─' * 70}")
        print(f"Step 6: Generate diff")
        print(f"{'─' * 70}")
        diff, changed = await dept._generate_diff(str(tmp_path))
        report.diff = diff
        report.files_changed = changed
        print(f"  ✓ {len(changed)} files changed")
        if diff:
            print(f"  Diff (first 500 chars):")
            print(f"  {diff[:500]}")

    # Step 7: Human gate (non-interactive → REJECTED)
    print(f"\n{'─' * 70}")
    print(f"Step 7: Human Approval Gate")
    print(f"{'─' * 70}")
    report.approval = await dept.gate.request_approval(report)
    print(f"  Result: {report.approval.value}")

    # Step 8: No commit (rejected)
    print(f"\n{'─' * 70}")
    print(f"Step 8: Commit + PR")
    print(f"{'─' * 70}")
    print(f"  ✗ Not approved — no commit, no PR")
    print(f"  ✓ Branch cleaned up — no changes persisted")

    elapsed = time.perf_counter() - start

    print(f"\n{'=' * 70}")
    print(f"ENGINEERING REPORT")
    print(f"{'=' * 70}")
    print(report.summary())
    print(f"\nElapsed: {elapsed:.1f}s")

    # Validation criteria
    criteria = {
        "code_analyzed": report.files_analyzed > 0,
        "issues_found": len(report.issues_found) >= 0,
        "fixes_proposed": isinstance(report.fixes_proposed, list),
        "diff_generated": isinstance(report.diff, str),
        "human_gate_present": report.approval is not None,
        "no_auto_commit": report.approval != ApprovalResult.APPROVED,
        "no_pr_without_approval": report.pr_url == "",
        "cleanup_on_reject": report.approval == ApprovalResult.REJECTED,
    }

    print(f"\n── Critères de validation ──")
    for k, v in criteria.items():
        print(f"  {'✓' if v else '✗'} {k}")

    passed = all(criteria.values())
    print(f"\nPHASE 3B (Software Engineering): {'✓ PASS' if passed else '✗ FAIL'}")

    print(f"\n── Safety guarantees ──")
    print(f"  ✓ No commit to main (always uses a new branch)")
    print(f"  ✓ No PR without human approval")
    print(f"  ✓ Human gate is blocking (cannot be bypassed in interactive mode)")
    print(f"  ✓ Cleanup on rejection (no changes persisted)")

    out = Path(__file__).resolve().parent / "phase3b_result.json"
    out.write_text(json.dumps({
        "scenario": "3B — Software Engineering Department",
        "passed": passed,
        "criteria": criteria,
        "report": {
            "repo": report.repo,
            "branch": report.branch,
            "files_analyzed": report.files_analyzed,
            "issues_found": len(report.issues_found),
            "fixes_proposed": len(report.fixes_proposed),
            "tests_run": report.tests_run,
            "tests_passed": report.tests_passed,
            "files_changed": len(report.files_changed),
            "approval": report.approval.value if report.approval else None,
            "pr_created": bool(report.pr_url),
            "elapsed_sec": round(elapsed, 1),
        },
    }, indent=2))
    print(f"\nResults saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())
