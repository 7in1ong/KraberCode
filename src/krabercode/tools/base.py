"""
Base classes for KraberCode tools.

Defines the tool interface and result types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: str
    error: Optional[str] = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_string(self) -> str:
        """Convert result to string for LLM consumption."""
        if self.success:
            return self.output
        return f"Error: {self.error}\nOutput: {self.output}"


class Tool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Get the tool description."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """Get the parameter schema."""
        pass

    @property
    def required_parameters(self) -> list[str]:
        """Get the list of required parameters."""
        return []

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def to_openai_format(self) -> dict[str, Any]:
        """Convert tool to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required_parameters,
                },
            },
        }


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self) -> None:
        """Initialize the tool registry."""
        self._tools: dict[str, Tool] = {}
        self._handlers: dict[str, Callable] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def register_handler(self, name: str, handler: Callable) -> None:
        """Register a handler function for a tool."""
        self._handlers[name] = handler

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_handler(self, name: str) -> Optional[Callable]:
        """Get a handler by name."""
        return self._handlers.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_all_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format."""
        return [tool.to_openai_format() for tool in self._tools.values()]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{name}' not found",
            )

        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )


class FunctionTool(Tool):
    """Tool implementation using a function."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable,
        required: Optional[list[str]] = None,
    ) -> None:
        """Initialize function tool."""
        self._name = name
        self._description = description
        self._parameters = parameters
        self._handler = handler
        self._required = required or []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    @property
    def required_parameters(self) -> list[str]:
        return self._required

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the handler function."""
        try:
            # Check if handler is async
            import asyncio
            import inspect

            if inspect.iscoroutinefunction(self._handler):
                result = await self._handler(**kwargs)
            else:
                result = self._handler(**kwargs)

            if isinstance(result, ToolResult):
                return result

            return ToolResult(success=True, output=str(result))

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))