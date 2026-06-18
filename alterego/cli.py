"""ALTEREGO OS — CLI entrypoint (V1.1).

Usage:
  alterego run "Audit my VPS"
  alterego chat
  alterego plugins list
  alterego capabilities list
  alterego departments list
  alterego policy list
  alterego health
  alterego stats
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from alterego.kernel_factory import build_kernel

app = typer.Typer(
    name="alterego",
    help="ALTEREGO — Ton cerveau numérique externe",
    no_args_is_help=True,
)
console = Console()


@app.command()
def run(objective: str):
    """Run a single mission and print the result."""
    kernel = build_kernel()
    cos = kernel["chief_of_staff"]
    response = asyncio.run(cos.chat(objective))
    console.print(Panel(response, title="ALTEREGO", border_style="blue"))


@app.command()
def chat():
    """Interactive chat session."""
    kernel = build_kernel()
    cos = kernel["chief_of_staff"]
    console.print("[bold blue]ALTEREGO — chat mode[/bold blue] (type 'exit' to quit)\n")
    while True:
        msg = Prompt.ask("[bold green]You[/bold green]")
        if msg.lower() in {"exit", "quit", "q"}:
            break
        response = asyncio.run(cos.chat(msg))
        console.print(Panel(response, title="ALTEREGO", border_style="blue"))
        console.print()


@app.command(name="plugins")
def plugins_cmd(action: str = typer.Argument("list", help="list | capabilities")):
    """List loaded plugins or capabilities."""
    kernel = build_kernel()
    pm = kernel["plugin_manager"]
    if action == "list":
        table = Table(title="Plugins loaded")
        table.add_column("Name", style="cyan")
        table.add_column("Capabilities", style="green")
        table.add_column("Priority", style="yellow")
        for name in pm.list_plugins():
            p = pm.get(name)
            table.add_row(name, ", ".join(p.plugin_spec.capabilities), str(p.plugin_spec.priority))
        console.print(table)
    elif action == "capabilities":
        cap_reg = kernel["capability_registry"]
        table = Table(title="Capabilities available")
        table.add_column("Capability", style="cyan")
        table.add_column("Description", style="white")
        for cap in cap_reg.list():
            table.add_row(cap.name, cap.description)
        console.print(table)


@app.command()
def departments():
    """List loaded departments."""
    kernel = build_kernel()
    loader = kernel["department_loader"]
    table = Table(title="Departments loaded")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Capabilities", style="green")
    table.add_column("Roles", style="yellow")
    for d in loader.list():
        table.add_row(d.name, d.description, ", ".join(d.capabilities), ", ".join(d.roles))
    console.print(table)


@app.command()
def policy():
    """List active policy rules."""
    kernel = build_kernel()
    pe = kernel["policy_engine"]
    table = Table(title="Policy rules")
    table.add_column("Rule", style="cyan")
    table.add_column("Capability", style="white")
    table.add_column("Method", style="white")
    table.add_column("Risk", style="yellow")
    table.add_column("Decision", style="bold")
    for r in pe.list_rules():
        risk_color = {"low": "green", "medium": "yellow", "high": "red", "critical": "bold red"}.get(r["risk"], "white")
        decision_color = {"allow": "green", "require_approval": "yellow", "deny": "red"}.get(r["decision"], "white")
        table.add_row(
            r["name"],
            r.get("capability") or "*",
            r.get("method_pattern") or "*",
            f"[{risk_color}]{r['risk']}[/{risk_color}]",
            f"[{decision_color}]{r['decision']}[/{decision_color}]",
        )
    console.print(table)


@app.command()
def health():
    """Check the health of all plugins."""
    kernel = build_kernel()
    pm = kernel["plugin_manager"]
    table = Table(title="Plugin health")
    table.add_column("Plugin", style="cyan")
    table.add_column("Healthy", style="green")
    for name in pm.list_plugins():
        p = pm.get(name)
        try:
            ok = asyncio.run(p.health())
        except Exception:
            ok = False
        table.add_row(name, "✓" if ok else "✗")
    console.print(table)


@app.command()
def stats():
    """Show learning stats (mission success rates per capability)."""
    kernel = build_kernel()
    learning = kernel["learning_engine"]

    async def _show():
        stats = await learning.get_capability_stats()
        if not stats:
            console.print("[yellow]No missions recorded yet.[/yellow]")
            return
        table = Table(title="Capability success rates")
        table.add_column("Capability", style="cyan")
        table.add_column("Success", style="green")
        table.add_column("Failure", style="red")
        table.add_column("Rate", style="bold")
        for cap, s in sorted(stats.items()):
            total = s["success"] + s["failure"]
            rate = (s["success"] / total * 100) if total else 0
            rate_color = "green" if rate >= 90 else ("yellow" if rate >= 70 else "red")
            table.add_row(cap, str(s["success"]), str(s["failure"]), f"[{rate_color}]{rate:.0f}%[/{rate_color}]")
        console.print(table)

    asyncio.run(_show())


@app.command()
def feedback(mission_id: str, rating: int, comment: str = ""):
    """Give feedback on a mission (rating: -1, 0, or 1)."""
    kernel = build_kernel()
    learning = kernel["learning_engine"]
    asyncio.run(learning.record_user_feedback(mission_id, comment, rating))
    console.print(f"[green]✓ Feedback recorded for mission {mission_id} (rating={rating})[/green]")


@app.command()
def engineer(
    repo: str = typer.Argument(..., help="GitHub repo to analyze (owner/name)"),
    issue: str = typer.Option("", "--issue", "-i", help="Description of what to fix"),
    skip_approval: bool = typer.Option(False, "--skip-approval", help="DANGEROUS: skip human gate (testing only)"),
    no_test: bool = typer.Option(False, "--no-test", help="Skip running tests"),
):
    """Run the Software Engineering pipeline on a GitHub repo.

    Pipeline: Clone → Branch → Analyze → Fix → Test → Diff → Human Approval → Commit → PR

    ⚠ NO commits or PRs without explicit human approval.
    """
    from alterego.engineering import SoftwareEngineeringDepartment, HumanApprovalGate

    kernel = build_kernel()
    llm = kernel.get("llm_plugin")
    github = kernel["plugin_manager"].best_for("github")
    fs = kernel["plugin_manager"].best_for("filesystem")

    dept = SoftwareEngineeringDepartment(
        llm_plugin=llm,
        github_plugin=github,
        filesystem_plugin=fs,
        approval_gate=HumanApprovalGate(interactive=not skip_approval),
    )

    console.print(f"[bold blue]ALTEREGO — Software Engineering Department[/bold blue]")
    console.print(f"Repo: {repo}")
    console.print(f"Issue: {issue or '(general analysis)'}")
    console.print()

    report = asyncio.run(dept.run(
        repo=repo,
        issue_description=issue,
        auto_test=not no_test,
        skip_approval=skip_approval,
    ))

    console.print(Panel(report.summary(), title="Engineering Report", border_style="blue"))


@app.command()
def initiatives():
    """Run initiative scan and show detected opportunities/anomalies."""
    kernel = build_kernel()
    engine = kernel["initiative_engine"]

    async def _run():
        found = await engine.scan()
        if not found:
            console.print("[green]No initiatives detected. System is healthy.[/green]")
            return
        table = Table(title=f"Initiatives detected ({len(found)})")
        table.add_column("Type", style="cyan")
        table.add_column("Priority", style="yellow")
        table.add_column("Title", style="white")
        table.add_column("Description", style="dim")
        for init in found:
            table.add_row(init.type.value, init.priority.value, init.title, init.description[:80])
        console.print(table)

    asyncio.run(_run())


@app.command(name="twin")
def digital_twin_cmd():
    """Show your Digital Twin — what ALTEREGO knows about you."""
    kernel = build_kernel()
    twin = kernel["digital_twin"]

    async def _show():
        desc = await twin.describe()
        console.print(Panel(desc, title="Digital Twin", border_style="magenta"))

    asyncio.run(_show())


@app.command()
def register(
    entity: str = typer.Argument(..., help="project | server | objective"),
    name: str = typer.Argument(..., help="Name of the entity"),
    host: str = typer.Option("", "--host", help="Host (for servers)"),
):
    """Register a project, server, or objective in your Digital Twin."""
    kernel = build_kernel()
    twin = kernel["digital_twin"]

    async def _register():
        if entity == "project":
            await twin.register_project(name)
        elif entity == "server":
            if not host:
                console.print("[red]--host is required for servers[/red]")
                return
            await twin.register_server(name, host)
        elif entity == "objective":
            await twin.set_objective(name)
        else:
            console.print(f"[red]Unknown entity: {entity}. Use project, server, or objective.[/red]")
            return
        console.print(f"[green]✓ {entity} '{name}' registered[/green]")

    asyncio.run(_register())


@app.command()
def goal(
    action: str = typer.Argument(..., help="create | list | progress | complete"),
    title: str = typer.Argument("", help="Goal title (for create) or goal ID (for progress/complete)"),
    description: str = typer.Option("", "--desc", "-d", help="Goal description"),
    priority: int = typer.Option(50, "--priority", "-p", help="Priority 0-100"),
):
    """Manage persistent goals."""
    kernel = build_kernel()
    engine = kernel["goal_engine"]

    async def _run():
        if action == "create":
            if not title:
                console.print("[red]Goal title required[/red]")
                return
            await kernel["plugin_manager"].initialize_all()
            g = await engine.create_goal(title, description, priority)
            console.print(Panel(g.summary(), title=f"Goal Created: {g.id[:8]}", border_style="green"))
        elif action == "list":
            goals = await engine.list_goals()
            if not goals:
                console.print("[yellow]No goals registered. Use 'alterego goal create \"My Goal\"'[/yellow]")
                return
            table = Table(title=f"Goals ({len(goals)})")
            table.add_column("ID", style="dim")
            table.add_column("Title", style="cyan")
            table.add_column("Status", style="yellow")
            table.add_column("Progress", style="green")
            table.add_column("Priority", style="white")
            for g in goals:
                table.add_row(g.id[:8], g.title, g.status.value, f"{g.progress():.0%}", str(g.priority))
            console.print(table)
        elif action == "progress":
            report = await engine.summary()
            console.print(Panel(report, title="Goal Progress", border_style="blue"))
        elif action == "complete":
            if not title:
                console.print("[red]Goal ID required[/red]")
                return
            await engine.update_goal(title, status="completed")
            console.print(f"[green]✓ Goal {title} marked as completed[/green]")
        else:
            console.print(f"[red]Unknown action: {action}. Use create, list, progress, or complete.[/red]")

    asyncio.run(_run())


@app.command()
def brief():
    """Get the morning brief — what happened and what's planned."""
    kernel = build_kernel()

    async def _run():
        await kernel["plugin_manager"].initialize_all()
        daily = kernel["daily_assistant"]
        report = await daily.morning_brief()
        console.print(Panel(report, title="🌅 Morning Brief", border_style="yellow"))

    asyncio.run(_run())


@app.command()
def evening():
    """Get the evening report — what was accomplished today."""
    kernel = build_kernel()

    async def _run():
        await kernel["plugin_manager"].initialize_all()
        daily = kernel["daily_assistant"]
        report = await daily.evening_report()
        console.print(Panel(report, title="🌙 Evening Report", border_style="blue"))

    asyncio.run(_run())


@app.command()
def weekly():
    """Get the weekly review — progress and trends."""
    kernel = build_kernel()

    async def _run():
        await kernel["plugin_manager"].initialize_all()
        daily = kernel["daily_assistant"]
        report = await daily.weekly_review()
        console.print(Panel(report, title="📅 Weekly Review", border_style="magenta"))

    asyncio.run(_run)


@app.command()
def context():
    """Show the current context — what ALTEREGO knows about your current state."""
    kernel = build_kernel()

    async def _run():
        ctx_engine = kernel["context_engine"]
        summary = await ctx_engine.get_context_summary()
        console.print(Panel(summary, title="🧠 Current Context", border_style="cyan"))

    asyncio.run(_run)


@app.command(name="timeline")
def timeline_cmd(
    action: str = typer.Argument("summary", help="summary | today | recent | critical"),
    hours: int = typer.Option(24, "--hours", "-h", help="Hours to look back (for 'recent')"),
):
    """View the Life Timeline — ALTEREGO's living history."""
    kernel = build_kernel()
    tl = kernel["life_timeline"]

    async def _run():
        if action == "summary":
            report = await tl.summary(days=7)
        elif action == "today":
            events = await tl.get_today()
            report = f"Today's events ({len(events)}):\n" + "\n".join(
                f"  [{e.get('severity', '?')}] {e.get('title', '?')[:60]}" for e in events[:20]
            )
        elif action == "recent":
            events = await tl.get_recent(hours=hours)
            report = f"Last {hours}h ({len(events)} events):\n" + "\n".join(
                f"  [{e.get('severity', '?')}] {e.get('timestamp', '?')[:19]} {e.get('title', '?')[:50]}" for e in events[:20]
            )
        elif action == "critical":
            events = await tl.get_critical()
            report = f"Critical events ({len(events)}):\n" + "\n".join(
                f"  [{e.get('severity', '?')}] {e.get('timestamp', '?')[:19]} {e.get('title', '?')[:50]}" for e in events[:20]
            )
        else:
            report = f"Unknown action: {action}"
        console.print(Panel(report, title="📅 Life Timeline", border_style="magenta"))

    asyncio.run(_run())


@app.command(name="workspace")
def workspace_cmd():
    """Show the Unified Workspace — all connected tools in one view."""
    kernel = build_kernel()

    async def _run():
        await kernel["plugin_manager"].initialize_all()
        ws = kernel["unified_workspace"]
        desc = await ws.describe()
        console.print(Panel(desc, title="🌐 Unified Workspace", border_style="cyan"))

    asyncio.run(_run())


@app.command(name="remember")
def remember(query: str = typer.Argument(..., help="What to search for")):
    """Search long-term memory — find old ideas, conversations, decisions."""
    kernel = build_kernel()

    async def _run():
        ltm = kernel["long_term_memory"]
        result = await ltm.find_old_idea(query)
        console.print(Panel(result, title=f"🔍 Memory Search: '{query}'", border_style="yellow"))

    asyncio.run(_run)


@app.command(name="twin-v2")
def twin_v2_cmd():
    """Show Digital Twin V2 — complete knowledge graph."""
    kernel = build_kernel()
    twin = kernel["digital_twin_v2"]

    async def _run():
        desc = await twin.describe()
        console.print(Panel(desc, title="🧠 Digital Twin V2", border_style="magenta"))

    asyncio.run(_run)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
