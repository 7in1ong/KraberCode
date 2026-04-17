"""
Git tools for KraberCode.

Provides tools for Git repository operations.
"""

import subprocess
from pathlib import Path
from typing import Any

from krabercode.tools.base import Tool, ToolResult


class GitStatusTool(Tool):
    """Tool for getting Git repository status."""

    @property
    def name(self) -> str:
        return "git_status"

    @property
    def description(self) -> str:
        return "Get the status of a Git repository."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {
                "type": "string",
                "description": "Optional: Repository path (default: current directory).",
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute git status tool."""
        path = kwargs.get("path", ".")

        repo_path = Path(path)

        if not repo_path.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")

        # Check if it's a git repo
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Not a Git repository: {path}",
            )

        try:
            result = subprocess.run(
                ["git", "status", "--short", "--branch"],
                capture_output=True,
                text=True,
                cwd=str(repo_path),
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output=result.stderr,
                    error="git status failed",
                )

            return ToolResult(
                success=True,
                output=result.stdout,
                metadata={"path": str(repo_path)},
            )

        except FileNotFoundError:
            return ToolResult(success=False, output="", error="git command not found")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GitDiffTool(Tool):
    """Tool for getting Git diff."""

    @property
    def name(self) -> str:
        return "git_diff"

    @property
    def description(self) -> str:
        return "Get the diff of changes in a Git repository."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {
                "type": "string",
                "description": "Optional: Repository path.",
            },
            "staged": {
                "type": "boolean",
                "description": "Show staged changes (default: false, shows unstaged).",
            },
            "file": {
                "type": "string",
                "description": "Optional: Specific file to diff.",
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute git diff tool."""
        path = kwargs.get("path", ".")
        staged = kwargs.get("staged", False)
        file = kwargs.get("file")

        repo_path = Path(path)

        if not repo_path.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")

        try:
            cmd = ["git", "diff"]
            if staged:
                cmd.append("--staged")
            if file:
                cmd.append(file)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(repo_path),
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output=result.stderr,
                    error="git diff failed",
                )

            output = result.stdout
            if not output:
                output = "No changes"

            return ToolResult(
                success=True,
                output=output,
                metadata={"path": str(repo_path), "staged": staged},
            )

        except FileNotFoundError:
            return ToolResult(success=False, output="", error="git command not found")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GitLogTool(Tool):
    """Tool for getting Git log."""

    @property
    def name(self) -> str:
        return "git_log"

    @property
    def description(self) -> str:
        return "Get recent commit history from a Git repository."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {
                "type": "string",
                "description": "Optional: Repository path.",
            },
            "limit": {
                "type": "integer",
                "description": "Optional: Number of commits to show (default: 10).",
            },
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute git log tool."""
        path = kwargs.get("path", ".")
        limit = kwargs.get("limit", 10)

        repo_path = Path(path)

        if not repo_path.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")

        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--oneline", "--decorate"],
                capture_output=True,
                text=True,
                cwd=str(repo_path),
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output=result.stderr,
                    error="git log failed",
                )

            return ToolResult(
                success=True,
                output=result.stdout,
                metadata={"path": str(repo_path), "limit": limit},
            )

        except FileNotFoundError:
            return ToolResult(success=False, output="", error="git command not found")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))