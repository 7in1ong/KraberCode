"""
MCP (Model Context Protocol) integration for KraberCode.

Allows extending tool capabilities through MCP servers.
"""

from krabercode.mcp.client import MCPClient, MCPServerConnection
from krabercode.mcp.registry import MCPToolRegistry

__all__ = ["MCPClient", "MCPServerConnection", "MCPToolRegistry"]