from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(name="nexus", no_args_is_help=True)
console = Console()


@app.command()
def version() -> None:
    """Print Nexus version info."""
    import sys

    from nexus import __version__

    try:
        import civitas

        civitas_version = getattr(civitas, "__version__", "unknown")
    except ImportError:
        civitas_version = "not installed"

    console.print(f"Nexus {__version__}")
    console.print(f"Python {sys.version.split()[0]}")
    console.print(f"Civitas {civitas_version}")


_DEFAULT_CONFIG = typer.Option("config.yaml", "--config", "-c", help="Path to config file")


@app.command()
def run(
    config: Path = _DEFAULT_CONFIG,
) -> None:
    """Start the Nexus assistant."""
    from nexus.config import load_config

    try:
        cfg = load_config(config)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    import asyncio
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    console.print(f"[green]Config loaded:[/green] {config}")
    console.print(f"  LLM: {cfg.llm.model} @ {cfg.llm.base_url}")
    if cfg.telegram:
        console.print(f"  Telegram: configured ({len(cfg.telegram.allowed_user_ids)} users)")
    console.print(f"  Memory: {cfg.memory.db_path}")
    console.print(f"  Seed users: {len(cfg.seed_users)}")

    from nexus.runtime import run_nexus

    asyncio.run(run_nexus(cfg))


_DEFAULT_OUTPUT = typer.Option("config.yaml", "--output", "-o", help="Output config path")


@app.command()
def setup(
    output: Path = _DEFAULT_OUTPUT,
) -> None:
    """First-boot setup wizard — generates config.yaml interactively."""

    if output.exists():
        overwrite = typer.confirm(f"{output} already exists. Overwrite?", default=False)
        if not overwrite:
            raise typer.Exit()

    console.print("[bold]Nexus Setup[/bold]\n")

    bot_token = typer.prompt("Telegram bot token (from @BotFather)")
    api_key = typer.prompt("Anthropic API key")
    user_name = typer.prompt("Your name", default="User")
    telegram_id = typer.prompt("Your Telegram user ID (numeric)", type=int)
    timezone = typer.prompt("Your timezone", default="UTC")

    persona_choices = ["default", "dross"]
    console.print("\nAvailable personas:")
    for i, p in enumerate(persona_choices, 1):
        console.print(f"  [{i}] {p}")
    persona_idx = typer.prompt("Choose persona", type=int, default=1)
    persona = persona_choices[min(max(persona_idx, 1), len(persona_choices)) - 1]

    tenant_id = user_name.lower().replace(" ", "_")

    config_content = (
        f"llm:\n"
        f'  base_url: "http://localhost:4000"\n'
        f'  api_key: "{api_key}"\n'
        f'  model: "claude-sonnet-4-20250514"\n'
        f"  max_tokens: 4096\n"
        f"\n"
        f"telegram:\n"
        f'  bot_token: "{bot_token}"\n'
        f"  allowed_user_ids: [{telegram_id}]\n"
        f"\n"
        f"memory:\n"
        f'  db_path: "data/nexus.db"\n'
        f"\n"
        f'persona_dir: "personas"\n'
        f'users_dir: "data/users"\n'
        f'data_dir: "data"\n'
        f"\n"
        f"seed_users:\n"
        f'  - name: "{user_name}"\n'
        f'    tenant_id: "{tenant_id}"\n'
        f'    role: "admin"\n'
        f'    persona: "{persona}"\n'
        f'    timezone: "{timezone}"\n'
        f"    telegram_user_id: {telegram_id}\n"
    )

    output.write_text(config_content)
    console.print(f"\n[green]Config written to {output}[/green]")
    console.print(f"  Persona: {persona}")
    console.print(f"  User: {user_name} ({tenant_id})")
    console.print(f"\nRun [bold]nexus run --config {output}[/bold] to start.")


def main() -> None:
    app()
