"""
Context management for KraberCode agent.

Manages project context, conversation history, and memory.
"""

import os
from pathlib import Path
from typing import Optional


def gather_project_context(project_root: Path) -> str:
    """Gather context about the project."""
    context_parts = []
    
    # Check for common project files
    project_files = {
        "package.json": "Node.js/JavaScript project",
        "pyproject.toml": "Python project (modern)",
        "requirements.txt": "Python project (pip)",
        "Cargo.toml": "Rust project",
        "go.mod": "Go project",
        "pom.xml": "Java/Maven project",
        "build.gradle": "Java/Gradle project",
        "README.md": "Project documentation",
    }
    
    for filename, description in project_files.items():
        filepath = project_root / filename
        if filepath.exists():
            context_parts.append(f"- {filename}: {description}")
    
    # Check for source directories
    source_dirs = ["src", "lib", "app", "main", "server", "client"]
    for dir_name in source_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists() and dir_path.is_dir():
            # Count files
            file_count = len(list(dir_path.glob("**/*")))
            if file_count > 0:
                context_parts.append(f"- {dir_name}/: {file_count} source files")
    
    # Check for test directories
    test_dirs = ["tests", "test", "spec", "__tests__"]
    for dir_name in test_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists() and dir_path.is_dir():
            file_count = len(list(dir_path.glob("**/*")))
            if file_count > 0:
                context_parts.append(f"- {dir_name}/: {file_count} test files")
    
    if context_parts:
        return "\n".join(context_parts)
    return ""


class ContextManager:
    """Manages the agent's context window and memory."""
    
    def __init__(self, max_tokens: int = 100000):
        """Initialize context manager."""
        self.max_tokens = max_tokens
        self.system_prompt: Optional[str] = None
        self.conversation_history: list[dict] = []
        self.memory_items: list[str] = []
    
    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt."""
        self.system_prompt = prompt
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.conversation_history.append({"role": role, "content": content})
    
    def get_messages(self) -> list[dict]:
        """Get all messages for the LLM."""
        messages = []
        
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        
        messages.extend(self.conversation_history)
        
        return messages
    
    def estimate_tokens(self) -> int:
        """Estimate current token usage."""
        # Rough estimate: ~4 chars per token
        total_chars = len(self.system_prompt or "")
        for msg in self.conversation_history:
            total_chars += len(msg["content"])
        
        for item in self.memory_items:
            total_chars += len(item)
        
        return total_chars // 4
    
    def needs_truncation(self) -> bool:
        """Check if context needs truncation."""
        return self.estimate_tokens() > self.max_tokens
    
    def truncate_history(self) -> None:
        """Truncate conversation history to fit context window."""
        if not self.needs_truncation():
            return
        
        # Remove older messages, keeping recent ones
        while self.needs_truncation() and len(self.conversation_history) > 2:
            self.conversation_history.pop(0)  # Remove oldest user/assistant pair
    
    def add_memory(self, item: str) -> None:
        """Add an item to long-term memory."""
        self.memory_items.append(item)
        
        # Keep memory bounded
        max_memory_items = 20
        if len(self.memory_items) > max_memory_items:
            self.memory_items.pop(0)
    
    def clear(self) -> None:
        """Clear all context."""
        self.conversation_history.clear()
        self.memory_items.clear()