"""
Shell execution tools for KraberCode.

Provides tools for running shell commands safely.
"""

import asyncio
import os
import subprocess
from typing import Any

from krabercode.config.settings import get_settings
from krabercode.tools.base import Tool, ToolResult


class RunShellTool(Tool):
    """Tool for executing shell commands."""

    @property
    def name(self) -> str:
        return "run_shell"

    @property
    def description(self) -> str:
        return "Execute a shell command. Use with caution for system-modifying operations."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Optional: Timeout in seconds (default: 120).",
            },
            "cwd": {
                "type": "string",
                "description": "Optional: Working directory for the command.",
            },
        }

    @property
    def required_parameters(self) -> list[str]:
        return ["command"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the shell command tool."""
        command = kwargs.get("command")
        timeout = kwargs.get("timeout")
        cwd = kwargs.get("cwd")

        if not command:
            return ToolResult(success=False, output="", error="command is required")

        settings = get_settings()
        default_timeout = settings.tools.shell_timeout

        # Use provided timeout or default
        actual_timeout = timeout or default_timeout

        # Determine working directory
        working_dir = cwd if cwd else os.getcwd()

        # Check if command is allowed (if restrictions are set)
        if settings.tools.allowed_commands:
            cmd_name = command.split()[0] if command.split() else ""
            if cmd_name not in settings.tools.allowed_commands:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command '{cmd_name}' is not allowed",
                )

        try:
            # Run the command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=actual_timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {actual_timeout} seconds",
                )

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

            # Combine output
            output = stdout_str
            if stderr_str:
                output += f"\nSTDERR:\n{stderr_str}"

            # Determine success based on return code
            success = process.returncode == 0

            metadata = {
                "command": command,
                "return_code": process.returncode,
                "timeout": actual_timeout,
                "cwd": working_dir,
            }

            return ToolResult(
                success=success,
                output=output,
                error=None if success else f"Exit code: {process.returncode}",
                metadata=metadata,
            )

        except FileNotFoundError:
            return ToolResult(success=False, output="", error="Command not found")
        except PermissionError:
            return ToolResult(success=False, output="", error="Permission denied")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class RunBackgroundShellTool(Tool):
    """Tool for running shell commands in background."""

    @property
    def name(self) -> str:
        return "run_background"

    @property
    def description(self) -> str:
        return "Start a shell command in background. Returns process ID."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "command": {
                "type": "string",
                "description": "The shell command to run in background.",
            },
            "cwd": {
                "type": "string",
                "description": "Optional: Working directory.",
            },
        }

    @property
    def required_parameters(self) -> list[str]:
        return ["command"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute background shell tool."""
        command = kwargs.get("command")
        cwd = kwargs.get("cwd")

        if not command:
            return ToolResult(success=False, output="", error="command is required")

        working_dir = cwd if cwd else os.getcwd()

        try:
            # Create subprocess without waiting
            if os.name == "nt":
                # Windows
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                # Unix-like
                process = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=working_dir,
                    start_new_session=True,
                )

            metadata = {
                "command": command,
                "pid": process.pid,
                "cwd": working_dir,
            }

            return ToolResult(
                success=True,
                output=f"Started background process with PID {process.pid}",
                metadata=metadata,
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))