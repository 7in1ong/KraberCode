"""
MCP tool registry for KraberCode.

Registers MCP tools in the tool registry.
"""

from typing import Any, Optional

from krabercode.tools.base import Tool, ToolResult


class MCPToolWrapper(Tool):
    """Wrapper for MCP tools."""
    
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        server_name: str,
        mcp_client: Any,
    ) -> None:
        """Initialize MCP tool wrapper."""
        self._name = name
        self._description = description
        self._input_schema = input_schema
        self._server_name = server_name
        self._mcp_client = mcp_client
    
    @property
    def name(self) -> str:
        """Get tool name."""
        return f"mcp_{self._server_name}_{self._name}"
    
    @property
    def description(self) -> str:
        """Get tool description."""
        return f"[MCP:{self._server_name}] {self._description}"
    
    @property
    def parameters(self) -> dict[str, Any]:
        """Get parameter schema."""
        return self._input_schema.get("properties", {})
    
    @property
    def required_parameters(self) -> list[str]:
        """Get required parameters."""
        return self._input_schema.get("required", [])
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the MCP tool."""
        result = await self._mcp_client.call_tool(
            self._server_name,
            self._name,
            kwargs,
        )
        
        if "error" in result:
            return ToolResult(
                success=False,
                output="",
                error=result["error"],
            )
        
        return ToolResult(
            success=True,
            output=result.get("result", ""),
        )


class MCPToolRegistry:
    """Registry for MCP tools."""
    
    def __init__(self) -> None:
        """Initialize MCP tool registry."""
        self._mcp_tools: dict[str, MCPToolWrapper] = {}
        self._mcp_client: Optional[Any] = None
    
    async def register_mcp_tools(self, mcp_client: Any) -> None:
        """Register all tools from MCP client."""
        self._mcp_client = mcp_client
        
        tools = await mcp_client.get_all_tools()
        
        for tool_info in tools:
            wrapper = MCPToolWrapper(
                name=tool_info["name"],
                description=tool_info["description"],
                input_schema=tool_info["inputSchema"],
                server_name=tool_info["server"],
                mcp_client=mcp_client,
            )
            self._mcp_tools[wrapper.name] = wrapper
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get an MCP tool by name."""
        return self._mcp_tools.get(name)
    
    def list_tools(self) -> list[str]:
        """List all MCP tool names."""
        return list(self._mcp_tools.keys())
    
    def get_all_definitions(self) -> list[dict[str, Any]]:
        """Get all MCP tool definitions."""
        return [tool.to_openai_format() for tool in self._mcp_tools.values()]