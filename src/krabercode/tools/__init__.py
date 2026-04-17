"""
Tools module for KraberCode.

Provides built-in tools for file operations, shell execution, and more.
"""

from krabercode.tools.base import Tool, ToolResult, ToolRegistry
from krabercode.tools.registry import get_tool_registry, register_builtin_tools

__all__ = ["Tool", "ToolResult", "ToolRegistry", "get_tool_registry", "register_builtin_tools"]