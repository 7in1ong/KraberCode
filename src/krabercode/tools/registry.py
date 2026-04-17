"""
Tool registry for KraberCode.

Manages registration and execution of all available tools.
"""

from typing import Optional

from krabercode.tools.base import ToolRegistry
from krabercode.tools.filesystem import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    GlobTool,
    GrepTool,
    ListDirTool,
)
from krabercode.tools.shell import RunShellTool, RunBackgroundShellTool
from krabercode.tools.git import GitStatusTool, GitDiffTool, GitLogTool


# Global registry instance (initialize before function definition)
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        register_builtin_tools(_registry)
    return _registry


def register_builtin_tools(registry: ToolRegistry) -> None:
    """Register all built-in tools."""
    # File system tools
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(ListDirTool())

    # Shell tools
    registry.register(RunShellTool())
    registry.register(RunBackgroundShellTool())

    # Git tools
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitLogTool())


def register_custom_tool(
    registry: ToolRegistry,
    name: str,
    description: str,
    parameters: dict,
    handler,
    required: Optional[list[str]] = None,
) -> None:
    """Register a custom tool."""
    from krabercode.tools.base import FunctionTool

    tool = FunctionTool(
        name=name,
        description=description,
        parameters=parameters,
        handler=handler,
        required=required,
    )
    registry.register(tool)