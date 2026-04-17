"""
Output management for KraberCode.

Handles formatting, coloring, and display of responses using rich.
"""

from typing import Any, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from krabercode.config.settings import OutputSettings


class OutputManager:
    """Manages output formatting and display."""

    def __init__(
        self,
        console: Optional[Console] = None,
        settings: Optional[OutputSettings] = None,
    ) -> None:
        """Initialize output manager."""
        self.console = console or Console()
        self.settings = settings or OutputSettings()

    def print(self, content: str, style: Optional[str] = None) -> None:
        """Print text content."""
        if not self.settings.color:
            # Strip formatting for no-color mode
            self.console.print(content, style=None)
        else:
            self.console.print(content, style=style)

    def print_markdown(self, content: str) -> None:
        """Print markdown-formatted content."""
        if self.settings.format == "markdown":
            md = Markdown(content)
            self.console.print(md)
        else:
            self.console.print(content)

    def print_code(
        self,
        code: str,
        language: str = "python",
        line_numbers: bool = False,
    ) -> None:
        """Print code with syntax highlighting."""
        syntax = Syntax(
            code,
            language,
            line_numbers=line_numbers,
            theme="monokai" if self.settings.color else "default",
        )
        self.console.print(syntax)

    def print_panel(self, content: str, title: Optional[str] = None) -> None:
        """Print content in a panel."""
        panel = Panel(
            content,
            title=title,
            border_style="cyan" if self.settings.color else None,
        )
        self.console.print(panel)

    def print_table(self, headers: list[str], rows: list[list[Any]]) -> None:
        """Print content as a table."""
        table = Table(show_header=True, header_style="bold cyan")

        for header in headers:
            table.add_column(header)

        for row in rows:
            table.add_row(*[str(cell) for cell in row])

        self.console.print(table)

    def print_error(self, message: str) -> None:
        """Print an error message."""
        self.console.print(f"[bold red]Error:[/] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        self.console.print(f"[bold yellow]Warning:[/] {message}")

    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.console.print(f"[bold green]✓[/] {message}")

    def print_info(self, message: str) -> None:
        """Print an info message."""
        self.console.print(f"[bold blue]Info:[/] {message}")

    def print_debug(self, message: str) -> None:
        """Print a debug message (only if verbose mode)."""
        if self.settings.verbose:
            self.console.print(f"[dim]DEBUG: {message}[/]")

    def print_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Print token usage statistics."""
        if self.settings.show_tokens:
            total = input_tokens + output_tokens
            self.console.print(
                f"[dim]Tokens: {input_tokens} in + {output_tokens} out = {total} total[/]"
            )

    def print_tool_call(self, tool_name: str, args: dict[str, Any]) -> None:
        """Print tool call information."""
        args_str = ", ".join(f"{k}={v}" for k, v in args.items())
        self.console.print(f"[cyan]→ Tool:[/] {tool_name}({args_str})")

    def print_tool_result(self, result: Any, success: bool = True) -> None:
        """Print tool execution result."""
        status = "[green]✓[/]" if success else "[red]✗[/]"
        if isinstance(result, str):
            # Truncate long results
            display_result = result[:500] + "..." if len(result) > 500 else result
            self.console.print(f"{status} [dim]{display_result}[/]")
        else:
            self.console.print(f"{status} [dim]{result}[/]")

    def stream_response(self, token: str) -> None:
        """Stream a single token to output."""
        self.console.print(token, end="")

    def print_separator(self) -> None:
        """Print a separator line."""
        self.console.print("[dim]─[/]" * 50)

    def print_header(self, text: str) -> None:
        """Print a header."""
        self.console.print(f"\n[bold]{text}[/]\n")

    def format_file_path(self, path: str) -> Text:
        """Format a file path for display."""
        return Text(path, style="cyan")

    def format_command(self, command: str) -> Text:
        """Format a shell command for display."""
        return Text(command, style="yellow")