"""
KraberCode CLI commands.

Main entry point and command definitions using typer.
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from krabercode import __version__
from krabercode.cli.output import OutputManager
from krabercode.cli.repl import REPL
from krabercode.config.settings import get_settings
from krabercode.config.storage import ConfigStorage

app = typer.Typer(
    name="krabercode",
    help="KraberCode - A powerful CLI AI coding assistant",
    add_completion=True,
    no_args_is_help=False,
)

console = Console()
output = OutputManager()


@app.command()
def version() -> None:
    """Show KraberCode version."""
    console.print(f"KraberCode version: [bold green]{__version__}[/]")


@app.command()
def config(
    init: bool = typer.Option(False, "--init", "-i", help="Initialize default configuration files"),
    show: bool = typer.Option(False, "--show", "-s", help="Show current configuration"),
    keys: bool = typer.Option(False, "--keys", "-k", help="Show API keys status"),
    set_key: Optional[str] = typer.Option(
        None,
        "--set-key",
        help="Set API key for a provider (format: provider:key)",
    ),
    delete_key: Optional[str] = typer.Option(
        None,
        "--delete-key",
        help="Delete API key for a provider",
    ),
    edit: bool = typer.Option(False, "--edit", "-e", help="Open config file in editor"),
    path: bool = typer.Option(False, "--path", "-p", help="Show config file paths"),
) -> None:
    """Manage KraberCode configuration and API keys."""
    storage = ConfigStorage()

    # Initialize config files
    if init:
        storage.init_default_config()
        console.print("[green]✓[/] Configuration files created:")
        console.print(f"  • [cyan]{storage.config_file}[/]")
        console.print(f"  • [cyan]{storage.secrets_file}[/]")
        console.print(f"  • [cyan]{storage.mcp_config_file}[/]")
        console.print()
        console.print("[yellow]Tip:[/] Edit the secrets file to set your API keys")
        return

    # Show config file paths
    if path:
        console.print("[bold]Configuration Paths:[/]")
        console.print(f"  Config dir:    [cyan]{storage.config_dir}[/]")
        console.print(f"  Main config:   [cyan]{storage.config_file}[/]")
        console.print(f"  API keys:      [cyan]{storage.secrets_file}[/]")
        console.print(f"  MCP config:    [cyan]{storage.mcp_config_file}[/]")
        console.print(f"  History:       [cyan]{storage.history_file}[/]")
        return

    # Show API keys status
    if keys:
        console.print("[bold]API Keys Status:[/]")
        status = storage.list_api_keys_status()
        
        for provider, info in status.items():
            if info["has_key"]:
                icon = "[green]✓[/]"
                source = f"([dim]{info['source']}[/])"
            else:
                icon = "[red]✗[/]"
                source = f"([dim]set via {info['env_var']} or config file[/])"
            
            console.print(f"  {icon} [cyan]{provider}[/] {source}")
        
        console.print()
        console.print(f"[dim]Config file: {storage.secrets_file}[/]")
        return

    # Set API key
    if set_key:
        parts = set_key.split(":", 1)
        if len(parts) != 2:
            console.print("[red]Invalid format. Use: provider:key[/]")
            console.print("Example: [cyan]--set-key openai:sk-xxxx[/]")
            raise typer.Exit(1)
        provider, key = parts
        valid_providers = ["openai", "anthropic", "alibaba", "google"]
        if provider not in valid_providers:
            console.print(f"[red]Unknown provider: {provider}[/]")
            console.print(f"Valid providers: [cyan]{', '.join(valid_providers)}[/]")
            raise typer.Exit(1)
        storage.set_api_key(provider, key)
        console.print(f"[green]✓[/] API key set for [cyan]{provider}[/]")
        return

    # Delete API key
    if delete_key:
        valid_providers = ["openai", "anthropic", "alibaba", "google"]
        if delete_key not in valid_providers:
            console.print(f"[red]Unknown provider: {delete_key}[/]")
            raise typer.Exit(1)
        if storage.delete_api_key(delete_key):
            console.print(f"[green]✓[/] API key deleted for [cyan]{delete_key}[/]")
        else:
            console.print(f"[yellow]No API key found for {delete_key}[/]")
        return

    # Open config file in editor
    if edit:
        import subprocess
        import os
        
        editor = os.environ.get("EDITOR", "notepad" if os.name == "nt" else "nano")
        file_to_edit = storage.secrets_file
        
        console.print(f"Opening [cyan]{file_to_edit}[/] with [yellow]{editor}[/]...")
        try:
            subprocess.call([editor, str(file_to_edit)])
        except Exception as e:
            console.print(f"[red]Failed to open editor: {e}[/]")
            console.print(f"Manually edit: [cyan]{file_to_edit}[/]")
        return

    # Show current configuration
    if show:
        settings = get_settings()
        
        console.print("[bold]Model Settings:[/]")
        console.print(f"  Provider:     [cyan]{settings.model.provider}[/]")
        console.print(f"  Model:        [cyan]{settings.model.name}[/]")
        console.print(f"  Temperature:  {settings.model.temperature}")
        console.print(f"  Max Tokens:   {settings.model.max_tokens}")
        console.print(f"  Stream:       {settings.model.stream}")
        
        console.print()
        console.print("[bold]Output Settings:[/]")
        console.print(f"  Format:       {settings.output.format}")
        console.print(f"  Color:        {settings.output.color}")
        console.print(f"  Verbose:      {settings.output.verbose}")
        
        console.print()
        console.print("[bold]MCP Settings:[/]")
        console.print(f"  Enabled:      {settings.mcp.enabled}")
        
        console.print()
        console.print("[dim]Use --keys to see API key status[/]")
        return

    # Default: show help
    console.print("[bold]KraberCode Configuration[/]")
    console.print()
    console.print("Commands:")
    console.print("  [cyan]--init, -i[/]      Initialize configuration files")
    console.print("  [cyan]--show, -s[/]      Show current settings")
    console.print("  [cyan]--keys, -k[/]      Show API keys status")
    console.print("  [cyan]--set-key[/]       Set API key (provider:key)")
    console.print("  [cyan]--delete-key[/]    Delete API key for provider")
    console.print("  [cyan]--edit, -e[/]      Open secrets file in editor")
    console.print("  [cyan]--path, -p[/]      Show config file paths")
    console.print()
    console.print(f"Config directory: [cyan]{storage.config_dir}[/]")


@app.command()
def repl(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider to use"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
) -> None:
    """Start interactive REPL session."""
    settings = get_settings()

    # Override settings if specified
    if model:
        settings.model.name = model
    if provider:
        settings.model.provider = provider
    if debug:
        settings.debug = True

    console.print("[bold cyan]KraberCode REPL[/] - Interactive coding assistant")
    console.print(f"Model: [green]{settings.model.provider}/{settings.model.name}[/]")
    console.print("Type [yellow]/help[/] for commands, [yellow]/exit[/] to quit")
    console.print()

    repl_instance = REPL(console=console, output=output)
    asyncio.run(repl_instance.run())


@app.command()
def ask(
    prompt: str = typer.Argument(..., help="Question or task to ask the assistant"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider to use"),
    no_stream: bool = typer.Option(False, "--no-stream", help="Disable streaming"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="File to include in context"),
) -> None:
    """Ask a single question and get a response."""
    settings = get_settings()

    # Override settings if specified
    if model:
        settings.model.name = model
    if provider:
        settings.model.provider = provider
    if no_stream:
        settings.model.stream = False

    console.print(f"[dim]Using model: {settings.model.provider}/{settings.model.name}[/]")
    console.print()

    # Import here to avoid circular imports
    from krabercode.agent.executor import AgentExecutor

    executor = AgentExecutor(console=console, output=output)

    # Build the full prompt
    full_prompt = prompt
    if file and file.exists():
        content = file.read_text(encoding="utf-8")
        full_prompt = f"File: {file.name}\n\n```\n{content}\n```\n\n{prompt}"

    asyncio.run(executor.execute_single(full_prompt))


@app.command()
def tools(
    list_tools: bool = typer.Option(False, "--list", "-l", help="List available tools"),
    mcp_status: bool = typer.Option(False, "--mcp", help="Show MCP server status"),
) -> None:
    """Manage and inspect available tools."""
    if list_tools:
        console.print("[bold]Built-in Tools:[/]")
        console.print("  [cyan]read_file[/] - Read file contents")
        console.print("  [cyan]write_file[/] - Write/create file")
        console.print("  [cyan]edit_file[/] - Edit file (string replacement)")
        console.print("  [cyan]glob[/] - Search files by pattern")
        console.print("  [cyan]grep[/] - Search file contents")
        console.print("  [cyan]run_shell[/] - Execute shell command")
        console.print("  [cyan]list_dir[/] - List directory contents")
        console.print("  [cyan]git_status[/] - Git repository status")
        console.print("  [cyan]git_diff[/] - Git diff output")
        return

    if mcp_status:
        settings = get_settings()
        storage = ConfigStorage()
        mcp_config = storage.load_mcp_config()

        console.print("[bold]MCP Servers:[/]")
        if not mcp_config.get("servers"):
            console.print("  [dim]No MCP servers configured[/]")
            console.print(f"  Config file: [cyan]{storage.mcp_config_file}[/]")
        else:
            for name, config in mcp_config["servers"].items():
                console.print(f"  [cyan]{name}[/]: {config.get('command', 'N/A')}")
        return

    console.print("Use --list or --mcp to inspect tools")


# Default command: run REPL if no arguments
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider to use"),
) -> None:
    """KraberCode - CLI AI coding assistant."""
    if ctx.invoked_subcommand is not None:
        return
    
    # Start REPL when no subcommand is invoked
    ctx.invoke(repl, model=model, provider=provider)