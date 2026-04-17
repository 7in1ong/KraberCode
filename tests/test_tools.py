"""
Tests for KraberCode tools module.
"""

import pytest
from pathlib import Path
import tempfile
import asyncio

from krabercode.tools.base import ToolResult
from krabercode.tools.filesystem import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    GlobTool,
    ListDirTool,
)
from krabercode.tools.registry import get_tool_registry, register_builtin_tools


class TestFilesystemTools:
    """Test filesystem tools."""
    
    @pytest.mark.asyncio
    async def test_read_file(self, temp_file):
        """Test reading a file."""
        tool = ReadFileTool()
        result = await tool.execute(file_path=str(temp_file))
        
        assert result.success
        assert result.output == "test content"
    
    @pytest.mark.asyncio
    async def test_read_file_not_found(self, temp_dir):
        """Test reading a non-existent file."""
        tool = ReadFileTool()
        result = await tool.execute(file_path=str(temp_dir / "nonexistent.txt"))
        
        assert not result.success
        assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_write_file(self, temp_dir):
        """Test writing a file."""
        tool = WriteFileTool()
        file_path = temp_dir / "new_file.txt"
        
        result = await tool.execute(
            file_path=str(file_path),
            content="new content"
        )
        
        assert result.success
        assert file_path.exists()
        assert file_path.read_text() == "new content"
    
    @pytest.mark.asyncio
    async def test_edit_file(self, temp_file):
        """Test editing a file."""
        tool = EditFileTool()
        
        result = await tool.execute(
            file_path=str(temp_file),
            old_string="test",
            new_string="modified"
        )
        
        assert result.success
        assert temp_file.read_text() == "modified content"
    
    @pytest.mark.asyncio
    async def test_edit_file_not_found(self, temp_file):
        """Test editing with non-existent text."""
        tool = EditFileTool()
        
        result = await tool.execute(
            file_path=str(temp_file),
            old_string="nonexistent",
            new_string="replacement"
        )
        
        assert not result.success
    
    @pytest.mark.asyncio
    async def test_glob(self, temp_dir):
        """Test glob file search."""
        # Create some files
        (temp_dir / "test1.txt").write_text("content")
        (temp_dir / "test2.txt").write_text("content")
        (temp_dir / "other.py").write_text("content")
        
        tool = GlobTool()
        result = await tool.execute(pattern="*.txt", path=str(temp_dir))
        
        assert result.success
        assert "test1.txt" in result.output
        assert "test2.txt" in result.output
    
    @pytest.mark.asyncio
    async def test_list_dir(self, temp_dir):
        """Test listing directory."""
        (temp_dir / "file.txt").write_text("content")
        (temp_dir / "subdir").mkdir()
        
        tool = ListDirTool()
        result = await tool.execute(path=str(temp_dir))
        
        assert result.success
        assert "[FILE]" in result.output
        assert "[DIR]" in result.output


class TestToolRegistry:
    """Test tool registry."""
    
    def test_registry_creation(self):
        """Test creating tool registry."""
        registry = get_tool_registry()
        assert registry is not None
    
    def test_builtin_tools_registered(self):
        """Test that builtin tools are registered."""
        registry = get_tool_registry()
        tools = registry.list_tools()
        
        assert "read_file" in tools
        assert "write_file" in tools
        assert "edit_file" in tools
    
    @pytest.mark.asyncio
    async def test_execute_tool(self, temp_file):
        """Test executing a tool via registry."""
        registry = get_tool_registry()
        result = await registry.execute(
            "read_file",
            file_path=str(temp_file)
        )
        
        assert result.success
    
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Test executing an unknown tool."""
        registry = get_tool_registry()
        result = await registry.execute("unknown_tool")
        
        assert not result.success
        assert "not found" in result.error.lower()