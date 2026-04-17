"""
Interactive REPL for KraberCode.

Provides an interactive shell-like interface for continuous interaction
with the coding assistant.
"""

import asyncio
import os
import sys
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel

from krabercode.cli.output import OutputManager
from krabercode.config.storage import ConfigStorage


class REPL:
    """Interactive REPL session handler."""

    STYLE = Style.from_dict(
        {
            "prompt": "bold cyan",
            "": "#ffffff",
        }
    )

    COMMANDS = {
        "/help": "Show available commands",
        "/exit": "Exit REPL",
        "/quit": "Exit REPL",
        "/clear": "Clear screen",
        "/model": "Switch model (format: /model provider/name)",
        "/history": "Show conversation history",
        "/save": "Save conversation to file",
        "/config": "Show current configuration",
        "/tools": "List available tools",
        "/mcp": "Show MCP server status",
    }

    def __init__(
        self,
        console: Optional[Console] = None,
        output: Optional[OutputManager] = None,
    ) -> None:
        """Initialize REPL with console and output manager."""
        self.console = console or Console()
        self.output = output or OutputManager()
        self.storage = ConfigStorage()

        # History file
        history_path = self.storage.config_dir / "input_history"
        self.history = FileHistory(str(history_path))

        # Prompt session
        self.session: Optional[PromptSession] = None

        # Key bindings
        self.key_bindings = KeyBindings()

        # Conversation history
        self.conversation: list[dict[str, str]] = []

        # Agent executor (lazy loaded)
        self._executor = None

    def _get_executor(self):
        """Lazy load the agent executor."""
        if self._executor is None:
            from krabercode.agent.executor import AgentExecutor
            self._executor = AgentExecutor(console=self.console, output=self.output)
        return self._executor

    async def run(self) -> None:
        """Run the REPL session."""
        self.session = PromptSession(
            history=self.history,
            style=self.STYLE,
            key_bindings=self.key_bindings,
            mouse_support=True,
            multiline=True,
            prompt_continuation="... ",
        )

        while True:
            try:
                # Get user input
                user_input = await self.session.prompt_async(
                    "krabercode> ",
                )

                # Handle empty input
                if not user_input.strip():
                    continue

                # Handle commands
                if user_input.strip().startswith("/"):
                    await self._handle_command(user_input.strip())
                    continue

                # Handle regular prompt
                await self._handle_prompt(user_input)

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use /exit to quit[/]")
                continue

            except EOFError:
                # Ctrl+D
                self.console.print("\n[green]Goodbye![/]")
                break

    async def _handle_command(self, command: str) -> None:
        """Handle REPL commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else None

        if cmd in ("/exit", "/quit"):
            self.console.print("[green]Goodbye![/]")
            sys.exit(0)

        elif cmd == "/help":
            self._show_help()

        elif cmd == "/clear":
            self.console.clear()

        elif cmd == "/model":
            await self._change_model(args)

        elif cmd == "/history":
            self._show_history()

        elif cmd == "/save":
            await self._save_conversation(args)

        elif cmd == "/config":
            self._show_config()

        elif cmd == "/tools":
            self._show_tools()

        elif cmd == "/mcp":
            self._show_mcp_status()

        else:
            self.console.print(f"[red]Unknown command: {cmd}[/]")
            self.console.print("Type [yellow]/help[/] for available commands")

    def _show_help(self) -> None:
        """Show available commands."""
        help_text = "\n".join(
            f"  [cyan]{cmd}[/] - {desc}" for cmd, desc in self.COMMANDS.items()
        )
        self.console.print(Panel(help_text, title="[bold]Commands[/]", border_style="cyan"))

    async def _change_model(self, args: Optional[str]) -> None:
        """Change the current model."""
        if not args:
            self.console.print("[red]Usage: /model provider/name[/]")
            self.console.print("Example: [cyan]/model openai/gpt-4[/]")
            return

        try:
            provider, model_name = args.split("/")
            from krabercode.config.settings import get_settings
            settings = get_settings()
            settings.model.provider = provider
            settings.model.name = model_name
            self.console.print(f"[green]✓[/] Switched to [cyan]{provider}/{model_name}[/]")
        except ValueError:
            self.console.print("[red]Invalid format. Use: provider/name[/]")

    def _show_history(self) -> None:
        """Show conversation history."""
        if not self.conversation:
            self.console.print("[dim]No conversation history[/]")
            return

        self.console.print("[bold]Conversation History:[/]")
        for i, msg in enumerate(self.conversation, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100]
            color = "cyan" if role == "user" else "green"
            self.console.print(f"  [{color}]{role}[/]: {content}...")

    async def _save_conversation(self, args: Optional[str]) -> None:
        """Save conversation to file."""
        if not self.conversation:
            self.console.print("[dim]No conversation to save[/]")
            return

        filename = args or "conversation.json"
        if not filename.endswith(".json"):
            filename += ".json"

        import json
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.conversation, f, ensure_ascii=False, indent=2)

        self.console.print(f"[green]✓[/] Saved conversation to [cyan]{filename}[/]")

    def _show_config(self) -> None:
        """Show current configuration."""
        from krabercode.config.settings import get_settings
        settings = get_settings()

        config_text = f"""
  Model: [cyan]{settings.model.provider}/{settings.model.name}[/]
  Temperature: {settings.model.temperature}
  Max Tokens: {settings.model.max_tokens}
  Stream: {settings.model.stream}
  MCP Enabled: {settings.mcp.enabled}
  Output Format: {settings.output.format}
"""
        self.console.print(Panel(config_text, title="[bold]Configuration[/]", border_style="cyan"))

    def _show_tools(self) -> None:
        """Show available tools."""
        tools_text = """
  [cyan]read_file[/] - Read file contents
  [cyan]write_file[/] - Write/create file
  [cyan]edit_file[/] - Edit file (string replacement)
  [cyan]glob[/] - Search files by pattern
  [cyan]grep[/] - Search file contents
  [cyan]run_shell[/] - Execute shell command
  [cyan]list_dir[/] - List directory contents
  [cyan]git_status[/] - Git repository status
  [cyan]git_diff[/] - Git diff output
"""
        self.console.print(Panel(tools_text, title="[bold]Available Tools[/]", border_style="cyan"))

    def _show_mcp_status(self) -> None:
        """Show MCP server status."""
        mcp_config = self.storage.load_mcp_config()

        if not mcp_config.get("servers"):
            self.console.print("[dim]No MCP servers configured[/]")
            return

        status_text = "\n".join(
            f"  [cyan]{name}[/]: {config.get('command', 'N/A')}"
            for name, config in mcp_config["servers"].items()
        )
        self.console.print(Panel(status_text, title="[bold]MCP Servers[/]", border_style="cyan"))

    async def _handle_prompt(self, prompt: str) -> None:
        """Handle a regular user prompt."""
        # Add to conversation history
        self.conversation.append({"role": "user", "content": prompt})

        # Get response from agent
        executor = self._get_executor()
        response = await executor.execute(prompt, conversation=self.conversation)

        # Add response to history
        if response:
            self.conversation.append({"role": "assistant", "content": response})