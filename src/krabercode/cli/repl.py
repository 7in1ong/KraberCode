"""
Interactive REPL for KraberCode.

Provides an interactive shell-like interface with:
- Command auto-completion
- First-time setup guidance
- Rich output formatting
"""

import asyncio
import sys
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from krabercode.cli.output import OutputManager
from krabercode.config.storage import ConfigStorage


class CommandCompleter(Completer):
    """Auto-completer for REPL commands."""
    
    COMMANDS = {
        "/help": "Show available commands",
        "/exit": "Exit REPL",
        "/quit": "Exit REPL",
        "/clear": "Clear screen",
        "/model": "Switch model (e.g., /model openai/gpt-4o)",
        "/baseurl": "Set custom API base URL (e.g., /baseurl openai:https://...)",
        "/plan": "Manage coding plans (e.g., /plan interactive)",
        "/history": "Show conversation history",
        "/save": "Save conversation to file",
        "/config": "Show current configuration",
        "/keys": "Show API keys status",
        "/setkey": "Set API key (e.g., /setkey openai:sk-xxx)",
        "/tools": "List available tools",
        "/mcp": "Show MCP server status",
    }
    
    def get_completions(self, document, complete_event):
        """Return completions for current input."""
        text = document.text_before_cursor
        
        # Only complete commands starting with /
        if not text.startswith("/"):
            return
        
        # Find matching commands
        for cmd, desc in self.COMMANDS.items():
            if cmd.startswith(text):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=desc,
                )


class REPL:
    """Interactive REPL session handler with enhanced UX."""

    STYLE = Style.from_dict(
        {
            "prompt": "bold cyan",
            "": "#ffffff",
        }
    )

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

        # Prompt session with auto-completion
        self.session: Optional[PromptSession] = None

        # Conversation history
        self.conversation: list[dict[str, str]] = []

        # Agent executor (lazy loaded)
        self._executor = None
        
        # First-time setup flag
        self._is_first_run = not self.storage.config_file.exists()

    def _get_executor(self):
        """Lazy load the agent executor."""
        if self._executor is None:
            from krabercode.agent.executor import AgentExecutor
            self._executor = AgentExecutor(console=self.console, output=self.output)
        return self._executor
    
    def _check_api_keys(self) -> bool:
        """Check if any API key is configured."""
        status = self.storage.list_api_keys_status()
        return any(info["has_key"] for info in status.values())
    
    def _show_welcome(self) -> None:
        """Show welcome screen with setup guidance."""
        self.console.print()
        self.console.print(Panel(
            "[bold cyan]KraberCode[/] - Your AI Coding Assistant\n"
            "[dim]Version 0.1.0[/]",
            border_style="cyan",
        ))
        self.console.print()
        
        # Check API keys
        if not self._check_api_keys():
            self.console.print("[yellow]⚠ No API key configured![/]")
            self.console.print()
            self.console.print("To use KraberCode, you need to set an API key:")
            self.console.print()
            
            # Show provider options
            table = Table(show_header=True, header_style="bold")
            table.add_column("Provider", style="cyan")
            table.add_column("Example Model")
            table.add_column("Command")
            
            table.add_row("OpenAI", "gpt-4o", "/setkey openai:sk-xxx")
            table.add_row("Anthropic", "claude-3", "/setkey anthropic:sk-xxx")
            table.add_row("Alibaba (Qwen)", "qwen-max", "/setkey alibaba:xxx")
            table.add_row("Google (Gemini)", "gemini-pro", "/setkey google:xxx")
            
            self.console.print(table)
            self.console.print()
            self.console.print("[dim]Tip: You can also set keys via environment variables[/]")
            self.console.print("[dim]  OPENAI_API_KEY, ANTHROPIC_API_KEY, DASHSCOPE_API_KEY, GOOGLE_API_KEY[/]")
            self.console.print()
        else:
            # Show current model
            from krabercode.config.settings import get_settings
            settings = get_settings()
            self.console.print(f"[green]✓[/] Model: [cyan]{settings.model.provider}/{settings.model.name}[/]")
            self.console.print()
        
        # Show quick commands
        self.console.print("[bold]Quick Commands:[/]")
        self.console.print("  [cyan]/help[/]     - Show all commands")
        self.console.print("  [cyan]/model[/]    - Switch model (e.g., /model openai/gpt-4o)")
        self.console.print("  [cyan]/keys[/]     - Check API key status")
        self.console.print("  [cyan]/tools[/]    - List available tools")
        self.console.print("  [cyan]/exit[/]     - Exit REPL")
        self.console.print()
        self.console.print("[dim]Type your question to start chatting, or use /help for more options[/]")
        self.console.print()

    async def run(self) -> None:
        """Run the REPL session."""
        # Show welcome screen
        self._show_welcome()
        
        # Initialize prompt session with auto-completion
        self.session = PromptSession(
            history=self.history,
            style=self.STYLE,
            completer=CommandCompleter(),
            complete_while_typing=True,
            mouse_support=True,
            multiline=False,
            prompt_continuation="... ",
        )
        
        # Track consecutive Ctrl+C presses for exit
        ctrl_c_count = 0

        while True:
            try:
                # Reset Ctrl+C counter on normal input
                ctrl_c_count = 0
                
                # Get user input with auto-completion
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

                # Check if API key is configured before processing prompt
                if not self._check_api_keys():
                    self.console.print("[yellow]⚠ Please configure an API key first[/]")
                    self.console.print("Use [cyan]/setkey provider:key[/] or [cyan]/help[/] for instructions")
                    continue

                # Handle regular prompt
                await self._handle_prompt(user_input)

            except KeyboardInterrupt:
                ctrl_c_count += 1
                if ctrl_c_count >= 2:
                    # Double Ctrl+C to exit
                    self.console.print("\n[green]Goodbye![/]")
                    break
                else:
                    # First Ctrl+C shows hint
                    self.console.print("\n[yellow]Press Ctrl+C again to exit, or use /exit[/]")
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
            self._show_welcome()

        elif cmd == "/model":
            self._change_model(args)

        elif cmd == "/baseurl":
            self._set_base_url(args)

        elif cmd == "/plan":
            self._handle_plan(args)

        elif cmd == "/keys":
            self._show_keys_status()

        elif cmd == "/setkey":
            self._set_api_key(args)
            
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
            # Suggest similar commands
            self.console.print(f"[red]Unknown command: {cmd}[/]")
            similar = [c for c in CommandCompleter.COMMANDS if c.startswith(cmd[:3])]
            if similar:
                self.console.print(f"[dim]Did you mean: [cyan]{similar[0]}[/]?[/]")
            self.console.print("Type [yellow]/help[/] for available commands")

    def _show_help(self) -> None:
        """Show available commands with descriptions."""
        table = Table(show_header=True, header_style="bold cyan", border_style="cyan")
        table.add_column("Command", style="cyan", width=12)
        table.add_column("Description")
        
        for cmd, desc in CommandCompleter.COMMANDS.items():
            table.add_row(cmd, desc)
        
        self.console.print(Panel(table, title="[bold]Available Commands[/]", border_style="cyan"))

    def _change_model(self, args: Optional[str]) -> None:
        """Change the current model."""
        if not args:
            self.console.print("[red]Usage: /model provider/name[/]")
            self.console.print("Examples:")
            self.console.print("  [cyan]/model openai/gpt-4o[/]")
            self.console.print("  [cyan]/model anthropic/claude-3[/]")
            self.console.print("  [cyan]/model alibaba/qwen-max[/]")
            return

        try:
            provider, model_name = args.split("/")
            valid_providers = ["openai", "anthropic", "alibaba", "google"]
            if provider not in valid_providers:
                self.console.print(f"[red]Unknown provider: {provider}[/]")
                self.console.print(f"Valid: [cyan]{', '.join(valid_providers)}[/]")
                return
            
            from krabercode.config.settings import get_settings
            settings = get_settings()
            settings.model.provider = provider
            settings.model.name = model_name
            self.console.print(f"[green]✓[/] Switched to [cyan]{provider}/{model_name}[/]")
        except ValueError:
            self.console.print("[red]Invalid format. Use: provider/name[/]")

    def _set_base_url(self, args: Optional[str]) -> None:
        """Set custom base URL for a provider."""
        if not args:
            self.console.print("[red]Usage: /baseurl provider:url[/]")
            self.console.print("Examples:")
            self.console.print("  [cyan]/baseurl openai:http://localhost:8080/v1[/]")
            self.console.print("  [cyan]/baseurl custom:https://your-api.com/v1[/]")
            self.console.print()
            self.console.print("[dim]For OpenAI/Anthropic compatible APIs (vLLM, Ollama, etc.)[/]")
            return

        parts = args.split(":", 1)
        if len(parts) != 2:
            self.console.print("[red]Invalid format. Use: provider:url[/]")
            return

        provider, base_url = parts
        valid_providers = ["openai", "anthropic", "custom"]
        if provider not in valid_providers:
            self.console.print(f"[red]Unknown provider: {provider}[/]")
            self.console.print(f"Valid for base_url: [cyan]{', '.join(valid_providers)}[/]")
            return

        self.storage.set_base_url(provider, base_url)
        self.console.print(f"[green]✓[/] Base URL set for [cyan]{provider}[/]")
        self.console.print(f"  URL: [dim]{base_url}[/]")

    def _handle_plan(self, args: Optional[str]) -> None:
        """Handle coding plan commands."""
        if not args:
            # Show current plan status
            active_plan = self.storage.get_active_plan()
            plans = self.storage.list_plans()
            
            if not plans:
                self.console.print("[dim]No coding plans configured[/]")
                self.console.print("Use [cyan]/plan create name[/] to create a plan")
                return

            table = Table(show_header=True, header_style="bold")
            table.add_column("Plan", style="cyan")
            table.add_column("Mode")
            table.add_column("Description")
            table.add_column("Active")

            for name, config in plans.items():
                is_active = "✓" if name == active_plan else ""
                table.add_row(
                    name,
                    config.get("mode", "interactive"),
                    config.get("description", "")[:40],
                    is_active,
                )

            self.console.print(Panel(table, title="[bold]Coding Plans[/]", border_style="cyan"))
            self.console.print()
            self.console.print("Commands:")
            self.console.print("  [cyan]/plan name[/] - Switch to a plan")
            self.console.print("  [cyan]/plan create name[/] - Create new plan")
            self.console.print("  [cyan]/plan delete name[/] - Delete a plan")
            return

        # Parse subcommand
        parts = args.split(maxsplit=1)
        subcmd = parts[0]
        subargs = parts[1] if len(parts) > 1 else None

        if subcmd == "create":
            self._create_plan(subargs)
        elif subcmd == "delete":
            self._delete_plan(subargs)
        elif subcmd in self.storage.list_plans():
            # Switch to plan
            self.storage.set_active_plan(subcmd)
            plan_config = self.storage.get_plan_config(subcmd)
            self.console.print(f"[green]✓[/] Switched to plan [cyan]{subcmd}[/]")
            self.console.print(f"  Mode: {plan_config.get('mode', 'interactive')}")
            self.console.print(f"  Max iterations: {plan_config.get('max_iterations', 10)}")
        else:
            self.console.print(f"[red]Unknown plan or command: {subcmd}[/]")
            self.console.print("Available plans: [cyan]" + ", ".join(self.storage.list_plans().keys()) + "[/]")

    def _create_plan(self, args: Optional[str]) -> None:
        """Create a new coding plan."""
        if not args:
            self.console.print("[red]Usage: /plan create name[/]")
            return

        name = args.strip()
        self.storage.create_plan(
            name=name,
            description="Custom plan",
            mode="interactive",
            max_iterations=10,
            auto_confirm=False,
        )
        self.console.print(f"[green]✓[/] Created plan [cyan]{name}[/]")
        self.console.print("Edit config file to customize: [dim]" + str(self.storage.plan_file) + "[/]")

    def _delete_plan(self, args: Optional[str]) -> None:
        """Delete a coding plan."""
        if not args:
            self.console.print("[red]Usage: /plan delete name[/]")
            return

        name = args.strip()
        if self.storage.delete_plan(name):
            self.console.print(f"[green]✓[/] Deleted plan [cyan]{name}[/]")
        else:
            self.console.print(f"[red]Plan not found: {name}[/]")
    
    def _show_keys_status(self) -> None:
        """Show API keys status."""
        status = self.storage.list_api_keys_status()
        
        table = Table(show_header=True, header_style="bold")
        table.add_column("Provider", style="cyan")
        table.add_column("Status")
        table.add_column("Source")
        
        for provider, info in status.items():
            if info["has_key"]:
                status_str = "[green]✓ Configured[/]"
                source = info["source"]
            else:
                status_str = "[red]✗ Not set[/]"
                source = f"[dim]{info['env_var']}[/]"
            table.add_row(provider, status_str, source)
        
        self.console.print(Panel(table, title="[bold]API Keys Status[/]", border_style="cyan"))
        self.console.print()
        self.console.print(f"[dim]Config file: {self.storage.secrets_file}[/]")
        self.console.print("[dim]Use /setkey provider:key to configure[/]")

    def _set_api_key(self, args: Optional[str]) -> None:
        """Set API key for a provider."""
        if not args:
            self.console.print("[red]Usage: /setkey provider:key[/]")
            self.console.print("Examples:")
            self.console.print("  [cyan]/setkey openai:sk-xxxx[/]")
            self.console.print("  [cyan]/setkey alibaba:your-key[/]")
            return
        
        parts = args.split(":", 1)
        if len(parts) != 2:
            self.console.print("[red]Invalid format. Use: provider:key[/]")
            return
        
        provider, key = parts
        valid_providers = ["openai", "anthropic", "alibaba", "google"]
        if provider not in valid_providers:
            self.console.print(f"[red]Unknown provider: {provider}[/]")
            self.console.print(f"Valid: [cyan]{', '.join(valid_providers)}[/]")
            return
        
        self.storage.set_api_key(provider, key)
        self.console.print(f"[green]✓[/] API key set for [cyan]{provider}[/]")
        self.console.print("[dim]Key saved to secrets.yaml[/]")

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
  [cyan]read_file[/]    - Read file contents
  [cyan]write_file[/]   - Write/create file
  [cyan]edit_file[/]    - Edit file (string replacement)
  [cyan]glob[/]         - Search files by pattern
  [cyan]grep[/]         - Search file contents
  [cyan]run_shell[/]    - Execute shell command
  [cyan]list_dir[/]     - List directory contents
  [cyan]git_status[/]   - Git repository status
  [cyan]git_diff[/]     - Git diff output
  [cyan]git_log[/]      - Git commit history
"""
        self.console.print(Panel(tools_text, title="[bold]Available Tools[/]", border_style="cyan"))

    def _show_mcp_status(self) -> None:
        """Show MCP server status."""
        mcp_config = self.storage.load_mcp_config()

        if not mcp_config.get("servers"):
            self.console.print("[dim]No MCP servers configured[/]")
            self.console.print(f"[dim]Config file: {self.storage.mcp_config_file}[/]")
            return

        table = Table(show_header=True, header_style="bold")
        table.add_column("Server", style="cyan")
        table.add_column("Command")
        
        for name, config in mcp_config["servers"].items():
            table.add_row(name, config.get("command", "N/A"))
        
        self.console.print(Panel(table, title="[bold]MCP Servers[/]", border_style="cyan"))

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