"""
LLM module for KraberCode.

Provides unified interface for multiple LLM providers using litellm.
"""

from krabercode.llm.base import LLMClient, LLMResponse
from krabercode.llm.messages import Message, MessageRole, ToolCall
from krabercode.llm.client import get_llm_client

__all__ = ["LLMClient", "LLMResponse", "Message", "MessageRole", "ToolCall", "get_llm_client"]