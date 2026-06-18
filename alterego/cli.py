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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
