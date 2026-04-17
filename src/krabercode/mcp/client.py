"""
MCP client implementation for KraberCode.

Connects to MCP servers and discovers available tools.
"""

import asyncio
import json
from typing import Any, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from krabercode.config.settings import get_settings
from krabercode.config.storage import ConfigStorage


class MCPServerConnection:
    """Represents a connection to an MCP server."""
    
    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] = None,
        env: dict[str, str] = None,
    ) -> None:
        """Initialize server connection."""
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.session: Optional[Any] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """Connect to the MCP server."""
        if not MCP_AVAILABLE:
            return False
        
        try:
            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env={**self.env, **dict(zip(["PATH"], [""]))},
            )
            
            read, write = await stdio_client(server_params)
            self.session = ClientSession(read, write)
            await self.session.initialize()
            self._connected = True
            return True
            
        except Exception:
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the server."""
        if self.session:
            try:
                await self.session.close()
            except Exception:
                pass
        self.session = None
        self._connected = False
    
    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from the server."""
        if not self._connected or not self.session:
            return []
        
        try:
            result = await self.session.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }
                for tool in result.tools
            ]
        except Exception:
            return []
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool on the server."""
        if not self._connected or not self.session:
            return {"error": "Not connected to server"}
        
        try:
            result = await self.session.call_tool(tool_name, arguments)
            
            if result.isError:
                return {"error": result.content}
            
            # Extract content
            content = []
            for item in result.content:
                if hasattr(item, "text"):
                    content.append(item.text)
                else:
                    content.append(str(item))
            
            return {"result": "\n".join(content)}
            
        except Exception as e:
            return {"error": str(e)}
    
    @property
    def is_connected(self) -> bool:
        """Check if server is connected."""
        return self._connected


class MCPClient:
    """MCP client that manages multiple server connections."""
    
    def __init__(self) -> None:
        """Initialize MCP client."""
        self.settings = get_settings()
        self.storage = ConfigStorage()
        self.servers: dict[str, MCPServerConnection] = {}
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all configured MCP servers."""
        if not self.settings.mcp.enabled:
            return
        
        if not MCP_AVAILABLE:
            return
        
        # Load MCP config
        mcp_config = self.storage.load_mcp_config()
        
        # Connect to each server
        for name, config in mcp_config.get("servers", {}).items():
            server = MCPServerConnection(
                name=name,
                command=config.get("command", ""),
                args=config.get("args", []),
                env=config.get("env", {}),
            )
            
            connected = await server.connect()
            if connected:
                self.servers[name] = server
        
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Disconnect from all servers."""
        for server in self.servers.values():
            await server.disconnect()
        self.servers.clear()
    
    async def get_all_tools(self) -> list[dict[str, Any]]:
        """Get all tools from all connected servers."""
        all_tools = []
        
        for server in self.servers.values():
            tools = await server.list_tools()
            for tool in tools:
                tool["server"] = server.name
                all_tools.append(tool)
        
        return all_tools
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool on a specific server."""
        server = self.servers.get(server_name)
        if not server:
            return {"error": f"Server '{server_name}' not found"}
        
        return await server.call_tool(tool_name, arguments)
    
    def get_server_names(self) -> list[str]:
        """Get list of connected server names."""
        return list(self.servers.keys())
    
    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._initialized


# Global MCP client
_mcp_client: Optional[MCPClient] = None


async def get_mcp_client() -> MCPClient:
    """Get the global MCP client."""
    if _mcp_client is None:
        _mcp_client = MCPClient()
        await _mcp_client.initialize()
    return _mcp_client


async def shutdown_mcp_client() -> None:
    """Shutdown the global MCP client."""
    if _mcp_client:
        await _mcp_client.shutdown()
        _mcp_client = None