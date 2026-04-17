"""
LLM base interfaces and types.

Defines the abstract interface that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from krabercode.llm.messages import Message, ToolCall


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str
    model: str
    provider: str

    # Token counts
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Tool calls (if any)
    tool_calls: list[ToolCall] = field(default_factory=list)

    # Additional metadata
    finish_reason: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMStreamChunk:
    """A single chunk from a streaming LLM response."""

    content: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    finish_reason: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send messages to LLM and get a complete response."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Send messages to LLM and stream the response."""
        pass

    @abstractmethod
    async def count_tokens(self, messages: list[Message]) -> int:
        """Count tokens in a list of messages."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the current model name."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        pass


class ToolDefinition:
    """Definition of a tool that can be called by the LLM."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        required: Optional[list[str]] = None,
    ) -> None:
        """Initialize tool definition."""
        self.name = name
        self.description = description
        self.parameters = parameters
        self.required = required or []

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }