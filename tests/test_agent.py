"""
Tests for KraberCode agent module.
"""

import pytest
from pathlib import Path

from krabercode.agent.context import ContextManager
from krabercode.agent.planner import TaskPlanner
from krabercode.agent.history import HistoryManager
from krabercode.agent.system_prompt import get_default_system_prompt


class TestContextManager:
    """Test context manager."""
    
    def test_context_creation(self):
        """Test creating context manager."""
        context = ContextManager()
        assert context.max_tokens > 0
    
    def test_add_message(self):
        """Test adding messages."""
        context = ContextManager()
        context.add_message("user", "Hello")
        context.add_message("assistant", "Hi there")
        
        assert len(context.conversation_history) == 2
    
    def test_get_messages(self):
        """Test getting messages for LLM."""
        context = ContextManager()
        context.set_system_prompt("Test prompt")
        context.add_message("user", "Hello")
        
        messages = context.get_messages()
        assert len(messages) >= 2
    
    def test_token_estimation(self):
        """Test token estimation."""
        context = ContextManager()
        context.add_message("user", "This is a test message")
        
        tokens = context.estimate_tokens()
        assert tokens > 0
    
    def test_truncation(self):
        """Test history truncation."""
        context = ContextManager(max_tokens=100)
        
        # Add many messages
        for i in range(100):
            context.add_message("user", f"Message {i}" * 10)
        
        context.truncate_history()
        assert context.estimate_tokens() <= 100


class TestTaskPlanner:
    """Test task planner."""
    
    def test_planner_creation(self):
        """Test creating task planner."""
        planner = TaskPlanner()
        assert len(planner.tasks) == 0
    
    def test_create_plan(self):
        """Test creating a plan."""
        planner = TaskPlanner()
        tasks = planner.create_plan("1. Create file\n2. Edit file\n3. Run tests")
        
        assert len(tasks) >= 1
    
    def test_task_status(self):
        """Test task status management."""
        planner = TaskPlanner()
        planner.add_task("Test task")
        
        next_task = planner.get_next_task()
        assert next_task is not None
        assert next_task["status"] == "pending"
        
        planner.mark_in_progress(next_task["id"])
        task = planner.get_next_task()
        assert task["status"] == "in_progress"
    
    def test_status_summary(self):
        """Test status summary."""
        planner = TaskPlanner()
        planner.add_task("Task 1")
        planner.add_task("Task 2")
        planner.mark_completed("1")
        
        summary = planner.get_status_summary()
        assert "completed" in summary.lower()


class TestHistoryManager:
    """Test history manager."""
    
    def test_history_creation(self, temp_dir):
        """Test creating history manager."""
        history_file = temp_dir / "history.json"
        manager = HistoryManager(history_file)
        assert manager.history_file == history_file
    
    def test_add_entry(self, temp_dir):
        """Test adding history entry."""
        history_file = temp_dir / "history.json"
        manager = HistoryManager(history_file)
        
        manager.add_entry("user", "Test message")
        assert len(manager.entries) == 1
    
    def test_save_and_load(self, temp_dir):
        """Test saving and loading history."""
        history_file = temp_dir / "history.json"
        manager = HistoryManager(history_file)
        
        manager.add_entry("user", "Message 1")
        manager.add_entry("assistant", "Response 1")
        
        # Create new manager to load
        manager2 = HistoryManager(history_file)
        assert len(manager2.entries) == 2
    
    def test_search_history(self, temp_dir):
        """Test searching history."""
        history_file = temp_dir / "history.json"
        manager = HistoryManager(history_file)
        
        manager.add_entry("user", "Hello world")
        manager.add_entry("assistant", "Hi there")
        
        results = manager.search_history("hello")
        assert len(results) == 1


class TestSystemPrompt:
    """Test system prompt generation."""
    
    def test_default_prompt(self):
        """Test default prompt."""
        prompt = get_default_system_prompt()
        assert len(prompt) > 0
        assert "KraberCode" in prompt
    
    def test_prompt_contains_tools(self):
        """Test prompt mentions tools."""
        prompt = get_default_system_prompt()
        assert "read_file" in prompt
        assert "write_file" in prompt