"""ALTEREGO OS — CLI entrypoint.

Usage:
  alterego run "List the top 5 starred repos of vercel"
  alterego chat
  alterego plugins list
  alterego capabilities list
"""
from __future__ import annotations

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from alterego.kernel import (
    CapabilityRegistry,
    CapabilitySpec,
    ChiefOfStaff,
    DecisionEngine,
    InProcessEventBus,
    Memory,
    MissionEngine,
    Planner,
    PluginManager,
    SQLiteMemory,
)

app = typer.Typer(
    name="alterego",
    help="ALTEREGO OS — AI Operating System (V1)",
    no_args_is_help=True,
)
console = Console()


def _build_kernel() -> tuple[ChiefOfStaff, PluginManager, CapabilityRegistry, Memory]:
    """Wire up the full V1 kernel."""
    # 1. Infra
    memory = SQLiteMemory("./data/alterego.db")
    bus = InProcessEventBus()

    # 2. Plugins
    pm = PluginManager()
    pm.discover()
    asyncio.run(pm.initialize_all())

    # 3. Capabilities
    cap_reg = CapabilityRegistry()
    # Register capabilities based on what plugins are loaded
    _CAPABILITY_DESCRIPTIONS = {
        "github": "GitHub operations: clone, list_repos, get_repo_info, create_issue, create_pull_request, list_commits",
        "docker": "Docker: ps, logs, restart, stop, start, build, exec, stats",
        "ssh": "SSH: exec, scp_put, scp_get, health_check",
        "browser": "Browser: open, click, fill, screenshot, scrape, evaluate",
        "filesystem": "Filesystem: read, write, list, glob, copy, move, delete",
        "database.sql": "PostgreSQL: query, execute",
        "database.nosql": "MongoDB: find, insert, update, delete, count",
        "llm.chat": "LLM chat completion (OpenAI/Ollama)",
        "email": "Send email via SMTP",
        "telegram": "Send Telegram notifications",
    }
    for cap_name in pm.list_capabilities():
        cap_reg.register(CapabilitySpec(
            name=cap_name,
            description=_CAPABILITY_DESCRIPTIONS.get(cap_name, ""),
            required_plugins=[],  # filled implicitly via PluginManager
        ))

    # 4. Engines
    llm_plugin = pm.best_for("llm.chat")
    if not llm_plugin:
        console.print("[red]No LLM plugin loaded. Set OPENAI_API_KEY or OLLAMA_BASE_URL.[/red]")
        sys.exit(1)
    planner = Planner(capability_registry=cap_reg, llm_plugin=llm_plugin)
    decision = DecisionEngine(memory=memory, planner=planner, llm_plugin=llm_plugin)
    mission_engine = MissionEngine(memory=memory, event_bus=bus, decision_engine=decision, plugin_manager=pm)
    cos = ChiefOfStaff(mission_engine=mission_engine, memory=memory, event_bus=bus)
    return cos, pm, cap_reg, memory


@app.command()
def run(objective: str):
    """Run a single mission and print the result."""
    cos, _, _, _ = _build_kernel()
    response = asyncio.run(cos.chat(objective))
    console.print(Panel(response, title="ALTEREGO", border_style="blue"))


@app.command()
def chat():
    """Interactive chat session."""
    cos, _, _, _ = _build_kernel()
    console.print("[bold blue]ALTEREGO OS — chat mode[/bold blue] (type 'exit' to quit)\n")
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
    _, pm, cap_reg, _ = _build_kernel()
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
        table = Table(title="Capabilities available")
        table.add_column("Capability", style="cyan")
        table.add_column("Description", style="white")
        for cap in cap_reg.list():
            table.add_row(cap.name, cap.description)
        console.print(table)
    else:
        console.print(f"[red]Unknown action: {action}. Use 'list' or 'capabilities'.[/red]")


@app.command()
def health():
    """Check the health of all plugins."""
    _, pm, _, _ = _build_kernel()
    table = Table(title="Plugin health")
    table.add_column("Plugin", style="cyan")
    table.add_column("Healthy", style="green")
    for name in pm.list_plugins():
        p = pm.get(name)
        try:
            ok = asyncio.run(p.health())
        except Exception as e:
            ok = False
        table.add_row(name, "✓" if ok else "✗")
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
