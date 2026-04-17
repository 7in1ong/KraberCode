"""
File system tools for KraberCode.

Provides tools for reading, writing, editing, and searching files.
"""

import fnmatch
import os
import re
from pathlib import Path
from typing import Any, Optional

from krabercode.config.settings import get_settings
from krabercode.tools.base import Tool, ToolResult


class ReadFileTool(Tool):
    """Tool for reading file contents."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file. Returns the file content as a string."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to read.",
            },
            "offset": {
                "type": "integer",
                "description": "Optional: Line number to start reading from (0-based).",
            },
            "limit": {
                "type": "integer",
                "description": "Optional: Maximum number of lines to read.",
            },
        }

    @property
    def required_parameters(self) -> list[str]:
        return ["file_path"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the read file tool."""
        file_path = kwargs.get("file_path")
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit")

        if not file_path:
            return ToolResult(success=False, output="", error="file_path is required")

        path = Path(file_path)

        if not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {file_path}")

        if not path.is_file():
            return ToolResult(success=False, output="", error=f"Path is not a file: {file_path}")

        # Check file size
        settings = get_settings()
        file_size = path.stat().st_size
        if file_size > settings.tools.max_file_size:
            return ToolResult(
                success=False,
                output="",
                error=f"File too large: {file_size} bytes (max: {settings.tools.max_file_size})",
            )

        try:
            with open(path, encoding="utf-8") as f:
                if offset > 0 or limit:
                    lines = f.readlines()
                    if offset > 0:
                        lines = lines[offset:]
                    if limit:
                        lines = lines[:limit]
                    content = "".join(lines)
                else:
                    content = f.read()

            # Add metadata
            metadata = {
                "file_path": str(path),
                "file_size": file_size,
                "lines_read": len(content.splitlines()),
            }

            return ToolResult(success=True, output=content, metadata=metadata)

        except UnicodeDecodeError:
            return ToolResult(success=False, output="", error="File encoding error (not UTF-8)")
        except PermissionError:
            return ToolResult(success=False, output="", error="Permission denied")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(Tool):
    """Tool for writing file contents."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates the file if it doesn't exist, overwrites if it does."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to write.",
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file.",
            },
        }

    @property
    def required_parameters(self) -> list[str]:
        return ["file_path", "content"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the write file tool."""
        file_path = kwargs.get("file_path")
        content = kwargs.get("content")

        if not file_path:
            return ToolResult(success=False, output="", error="file_path is required")
        if content is None:
            return ToolResult(success=False, output="", error="content is required")

        path = Path(file_path)

        # Create parent directories if needed
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return ToolResult(success=False, output="", error="Cannot create parent directory")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            metadata = {
                "file_path": str(path),
                "bytes_written": len(content.encode("utf-8")),
            }

            return ToolResult(
                success=True,
                output=f"Successfully wrote to {file_path}",
                metadata=metadata,
            )

        except PermissionError:
            return ToolResult(success=False, output="", error="Permission denied")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class EditFileTool(Tool):
    """Tool for editing files by replacing text."""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Edit a file by replacing specific text. Use this for precise modifications."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to edit.",
            },
            "old_string": {
                "type": "string",
                "description": "The exact text to find and replace.",
            },
            "new_string": {
                "type": "string",
                "description": "The text to replace with.",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: false).",
            },
        }

    @property
    def required_parameters(self) -> list[str]:
        return ["file_path", "old_string", "new_string"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the edit file tool."""
        file_path = kwargs.get("file_path")
        old_string = kwargs.get("old_string")
        new_string = kwargs.get("new_string")
        replace_all = kwargs.get("replace_all", False)

        if not file_path:
            return ToolResult(success=False, output="", error="file_path is required")
        if not old_string:
            return ToolResult(success=False, output="", error="old_string is required")
        if new_string is None:
            return ToolResult(success=False, output="", error="new_string is required")

        path = Path(file_path)

        if not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {file_path}")

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()

            # Check if old_string exists
            if old_string not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Text not found in file: '{old_string[:50]}...'",
                )

            # Count occurrences
            count = content.count(old_string)

            # Replace
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replaced_count = count
            else:
                new_content = content.replace(old_string, new_string, 1)
                replaced_count = 1

            # Write back
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            metadata = {
                "file_path": str(path),
                "replacements": replaced_count,
                "total_occurrences": count,
            }

            return ToolResult(
                success=True,
                output=f"Replaced {replaced_count} occurrence(s) in {file_path}",
                metadata=metadata,
            )

        except PermissionError:
            return ToolResult(success=False, output="", error="Permission denied")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GlobTool(Tool):
    """Tool for searching files by pattern."""

    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return "Search for files matching a pattern. Uses glob syntax (e.g., '*.py', '**/*.txt')."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "pattern": {
                "type": "string",
                "description": "The glob pattern to search for.",
            },
            "path": {
                "type": "string",
                "description": "Optional: The directory to search in (default: current directory).",
            },
        }

    @property
    def required_parameters(self) -> list[str]:
        return ["pattern"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the glob tool."""
        pattern = kwargs.get("pattern")
        path = kwargs.get("path", ".")

        if not pattern:
            return ToolResult(success=False, output="", error="pattern is required")

        search_path = Path(path)

        if not search_path.exists():
            return ToolResult(success=False, output="", error=f"Directory not found: {path}")

        try:
            matches = list(search_path.glob(pattern))

            # Sort by modification time
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # Format output
            output_lines = [str(m) for m in matches[:100]]  # Limit to 100 results

            metadata = {
                "pattern": pattern,
                "path": str(search_path),
                "matches": len(matches),
                "returned": len(output_lines),
            }

            return ToolResult(
                success=True,
                output="\n".join(output_lines) if output_lines else "No matches found",
                metadata=metadata,
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GrepTool(Tool):
    """Tool for searching file contents."""

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return "Search for a pattern in file contents using regex."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "pattern": {
                "type": "string",
                "description": "The regex pattern to search for.",
            },
            "path": {
                "type": "string",
                "description": "Optional: Directory or file to search in.",
            },
            "glob": {
                "type": "string",
                "description": "Optional: File pattern to filter (e.g., '*.py').",
            },
        }

    @property
    def required_parameters(self) -> list[str]:
        return ["pattern"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the grep tool."""
        pattern = kwargs.get("pattern")
        path = kwargs.get("path", ".")
        glob_pattern = kwargs.get("glob", "*")

        if not pattern:
            return ToolResult(success=False, output="", error="pattern is required")

        search_path = Path(path)

        if not search_path.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")

        try:
            regex = re.compile(pattern)
            results = []

            # Get files to search
            if search_path.is_file():
                files = [search_path]
            else:
                files = list(search_path.glob(glob_pattern))

            for file_path in files:
                if not file_path.is_file():
                    continue

                try:
                    with open(file_path, encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(f"{file_path}:{line_num}: {line.rstrip()}")

                except (UnicodeDecodeError, PermissionError):
                    continue

            # Limit results
            output = "\n".join(results[:50])
            if len(results) > 50:
                output += f"\n... and {len(results) - 50} more results"

            metadata = {
                "pattern": pattern,
                "path": str(search_path),
                "matches": len(results),
            }

            return ToolResult(
                success=True,
                output=output if output else "No matches found",
                metadata=metadata,
            )

        except re.error as e:
            return ToolResult(success=False, output="", error=f"Invalid regex: {e}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirTool(Tool):
    """Tool for listing directory contents."""

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List contents of a directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "path": {
                "type": "string",
                "description": "The directory path to list.",
            },
        }

    @property
    def required_parameters(self) -> list[str]:
        return ["path"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the list directory tool."""
        path = kwargs.get("path")

        if not path:
            return ToolResult(success=False, output="", error="path is required")

        dir_path = Path(path)

        if not dir_path.exists():
            return ToolResult(success=False, output="", error=f"Directory not found: {path}")

        if not dir_path.is_dir():
            return ToolResult(success=False, output="", error=f"Path is not a directory: {path}")

        try:
            items = []
            for item in sorted(dir_path.iterdir()):
                if item.is_dir():
                    items.append(f"[DIR]  {item.name}/")
                else:
                    size = item.stat().st_size
                    items.append(f"[FILE] {item.name} ({size} bytes)")

            metadata = {
                "path": str(dir_path),
                "items": len(items),
            }

            return ToolResult(
                success=True,
                output="\n".join(items) if items else "Empty directory",
                metadata=metadata,
            )

        except PermissionError:
            return ToolResult(success=False, output="", error="Permission denied")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))