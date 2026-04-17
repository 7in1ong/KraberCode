"""
Agent module for KraberCode.

Handles the main agent loop, tool execution, and planning capabilities.
"""

from krabercode.agent.executor import AgentExecutor
from krabercode.agent.context import ContextManager
from krabercode.agent.planner import TaskPlanner
from krabercode.agent.history import HistoryManager
from krabercode.agent.system_prompt import SYSTEM_PROMPT, get_system_prompt, get_default_system_prompt

__all__ = [
    "AgentExecutor",
    "ContextManager",
    "TaskPlanner",
    "HistoryManager",
    "SYSTEM_PROMPT",
    "get_system_prompt",
    "get_default_system_prompt",
]