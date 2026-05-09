from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import civitas
import typer
from rich.console import Console

from nexus import __version__
from nexus.config import load_config
from nexus.runtime import run_nexus

app = typer.Typer(name="nexus", no_args_is_help=True)
console = Console()

_CIVITAS_VERSION = getattr(civitas, "__version__", "unknown")


@app.command()
def version() -> None:
    """Print Nexus version info."""
    console.print(f"Nexus {__version__}")
    console.print(f"Python {sys.version.split()[0]}")
    console.print(f"Civitas {_CIVITAS_VERSION}")


_DEFAULT_CONFIG = typer.Option("config.yaml", "--config", "-c", help="Path to config file")


@app.command()
def run(
    config: Path = _DEFAULT_CONFIG,
) -> None:
    """Start the Nexus assistant."""
    try:
        cfg = load_config(config)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    for noisy_logger in (
        "opentelemetry",
        "httpx",
        "httpcore",
        "aiosqlite",
        "telegram",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    os.environ.setdefault("OTEL_SDK_DISABLED", "true")

    console.print(f"[green]Config loaded:[/green] {config}")
    console.print(f"  LLM: {cfg.llm.model} @ {cfg.llm.base_url}")
    if cfg.telegram:
        console.print(f"  Telegram: configured ({len(cfg.telegram.allowed_user_ids)} users)")
    console.print(f"  Memory: {cfg.memory.db_path}")
    console.print(f"  Seed users: {len(cfg.seed_users)}")

    try:
        asyncio.run(run_nexus(cfg))
    except KeyboardInterrupt:
        console.print("\n[dim]Nexus stopped.[/dim]")


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


@app.command(name="setup-google")
def setup_google() -> None:
    """Set up Google Workspace MCP — OAuth credentials and Docker sidecar."""
    console.print("[bold]Google Workspace MCP Setup[/bold]\n")
    console.print("Prerequisites:")
    console.print("  1. Create a Google Cloud project")
    console.print("  2. Enable Gmail, Calendar, and Tasks APIs")
    console.print("  3. Create OAuth 2.0 credentials (Desktop app type)")
    console.print()

    client_id = typer.prompt("Google OAuth Client ID")
    client_secret = typer.prompt("Google OAuth Client Secret")
    google_email = typer.prompt("Google email address")

    env_path = Path(".env")
    existing = env_path.read_text() if env_path.exists() else ""

    env_vars = {
        "GOOGLE_OAUTH_CLIENT_ID": client_id,
        "GOOGLE_OAUTH_CLIENT_SECRET": client_secret,
        "GOOGLE_EMAIL": google_email,
    }

    additions = [f"{key}={value}" for key, value in env_vars.items() if key not in existing]

    if additions:
        with env_path.open("a") as f:
            f.write("\n".join(["", *additions, ""]))
        console.print(f"[green]Credentials added to {env_path}[/green]")

    console.print("\nNext steps:")
    console.print("  1. Start the MCP server:")
    console.print("     [bold]docker compose --profile google up -d --build[/bold]")
    console.print("  2. Trigger OAuth by sending a Google query to Nexus on Telegram")
    console.print("  3. Follow the auth URL that Nexus returns")
    console.print("  4. Set [bold]mcp.servers[0].enabled: true[/bold] in config.yaml")


_PERSONA_TEMPLATE = """\
# {name}

You are {name}, a personal AI assistant.

## Personality

{traits}

## Communication Style

- {formality_desc}
- Match the user's energy: brief question → brief answer, detailed question → detailed answer
{quirks}

## Values

- Reliability over speed — correct and slightly late beats fast and wrong
- Privacy is non-negotiable — never volunteer one user's info to another
- Transparency — say what you did and why

## Constraints

- Never send email, accept invite, or delete anything without approval
- Prefer reversible actions: archive over delete, draft over send
- If uncertain about user intent, ask — don't guess
"""

_FORMALITY_MAP = {
    "1": ("Very casual", "Talk like a close friend — contractions, slang OK"),
    "2": ("Casual-professional", "Professional but relaxed — no corporate speak"),
    "3": ("Professional", "Clear and structured — appropriate for work contexts"),
    "4": ("Very formal", "Formal language — no contractions, measured tone"),
}


@app.command(name="setup-persona")
def setup_persona() -> None:
    """Create a new persona (SOUL.md) interactively."""
    console.print("[bold]Persona Builder[/bold]\n")

    name = typer.prompt("Persona name (e.g., Dross, Friday)")
    traits_raw = typer.prompt("Personality in a few words (e.g., witty, direct, helpful)")

    console.print("\nFormality level:")
    for k, (label, _) in _FORMALITY_MAP.items():
        console.print(f"  [{k}] {label}")
    formality = typer.prompt("Choose", default="2")
    _, formality_desc = _FORMALITY_MAP.get(formality, _FORMALITY_MAP["2"])

    quirks_raw = typer.prompt("Any specific quirks or rules? (leave blank to skip)", default="")

    traits = "\n".join(f"- {t.strip()}" for t in traits_raw.split(",") if t.strip())
    quirks = "\n".join(f"- {q.strip()}" for q in quirks_raw.split(".") if q.strip())
    if quirks:
        quirks = "\n" + quirks

    content = _PERSONA_TEMPLATE.format(
        name=name,
        traits=traits,
        formality_desc=formality_desc,
        quirks=quirks,
    )

    safe_name = name.lower().replace(" ", "-")
    persona_path = Path("personas") / f"{safe_name}.md"
    persona_path.parent.mkdir(parents=True, exist_ok=True)
    persona_path.write_text(content)

    console.print(f"\n[green]Persona saved to {persona_path}[/green]")
    console.print(f"\nTo use it, set [bold]persona: {safe_name}[/bold] in your seed_users config.")


@app.command(name="personas")
def personas_cmd(
    action: str = typer.Argument("list", help="list or set"),
    name: str = typer.Argument("", help="Persona name (for set)"),
) -> None:
    """List or switch personas."""
    personas_dir = Path("personas")

    if action == "list":
        if not personas_dir.exists():
            console.print("[yellow]No personas directory found.[/yellow]")
            return
        for p in sorted(personas_dir.glob("*.md")):
            console.print(f"  {p.stem}")
        return

    if action == "set" and name:
        path = personas_dir / f"{name}.md"
        if not path.exists():
            console.print(f"[red]Persona '{name}' not found.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[green]Set persona to '{name}'.[/green]")
        console.print(f"Update [bold]persona: {name}[/bold] in config.yaml seed_users.")
        return

    console.print("[red]Usage: nexus personas list | nexus personas set <name>[/red]")


def main() -> None:
    app()
