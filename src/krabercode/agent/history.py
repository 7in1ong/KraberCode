"""
History management for KraberCode.

Handles conversation history persistence and retrieval.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class HistoryManager:
    """Manages conversation history."""
    
    def __init__(self, history_file: Optional[Path] = None):
        """Initialize history manager."""
        self.history_file = history_file
        self.entries: list[dict[str, Any]] = []
        
        if self.history_file and self.history_file.exists():
            self._load_history()
    
    def _load_history(self) -> None:
        """Load history from file."""
        try:
            with open(self.history_file, encoding="utf-8") as f:
                self.entries = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            self.entries = []
    
    def save(self) -> None:
        """Save history to file."""
        if not self.history_file:
            return
        
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)
    
    def add_entry(
        self,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """Add an entry to history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }
        self.entries.append(entry)
        
        # Limit history size
        max_entries = 100
        if len(self.entries) > max_entries:
            self.entries = self.entries[-max_entries:]
        
        self.save()
    
    def get_recent_entries(self, limit: int = 10) -> list[dict]:
        """Get recent history entries."""
        return self.entries[-limit:]
    
    def search_history(self, query: str) -> list[dict]:
        """Search history for matching entries."""
        results = []
        for entry in self.entries:
            if query.lower() in entry["content"].lower():
                results.append(entry)
        return results
    
    def clear(self) -> None:
        """Clear history."""
        self.entries.clear()
        self.save()