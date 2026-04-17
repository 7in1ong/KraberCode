"""
Message types for LLM communication.

Defines message formats, roles, and tool call structures.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MessageRole(Enum):
    """Role of a message in conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"  # Tool execution result


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }


@dataclass
class Message:
    """A message in the conversation."""

    role: MessageRole
    content: str

    # For assistant messages with tool calls
    tool_calls: list[ToolCall] = field(default_factory=list)

    # For tool response messages
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_openai_format(self) -> dict[str, Any]:
        """Convert message to OpenAI API format."""
        msg: dict[str, Any] = {
            "role": self.role.value,
        }

        if self.role == MessageRole.TOOL:
            msg["tool_call_id"] = self.tool_call_id
            msg["content"] = self.content
        elif self.tool_calls:
            # Assistant message with tool calls
            msg["content"] = self.content
            msg["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        else:
            msg["content"] = self.content

        return msg

    @classmethod
    def system(cls, content: str) -> "Message":
        """Create a system message."""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        """Create a user message."""
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(
        cls,
        content: str,
        tool_calls: Optional[list[ToolCall]] = None,
    ) -> "Message":
        """Create an assistant message."""
        return cls(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls or [],
        )

    @classmethod
    def tool_result(
        cls,
        content: str,
        tool_call_id: str,
        tool_name: str,
    ) -> "Message":
        """Create a tool result message."""
        return cls(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )


@dataclass
class Conversation:
    """A conversation with message history."""

    messages: list[Message] = field(default_factory=list)
    system_prompt: Optional[str] = None

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.add_message(Message.user(content))

    def add_assistant_message(
        self,
        content: str,
        tool_calls: Optional[list[ToolCall]] = None,
    ) -> None:
        """Add an assistant message."""
        self.add_message(Message.assistant(content, tool_calls))

    def add_tool_result(
        self,
        content: str,
        tool_call_id: str,
        tool_name: str,
    ) -> None:
        """Add a tool result message."""
        self.add_message(Message.tool_result(content, tool_call_id, tool_name))

    def get_messages_for_api(self) -> list[dict[str, Any]]:
        """Get messages in OpenAI API format."""
        messages = []

        if self.system_prompt:
            messages.append(Message.system(self.system_prompt).to_openai_format())

        for msg in self.messages:
            messages.append(msg.to_openai_format())

        return messages

    def clear(self) -> None:
        """Clear the conversation history."""
        self.messages.clear()

    def truncate(self, max_messages: int = 50) -> None:
        """Truncate conversation to max messages (keeping system prompt)."""
        if len(self.messages) > max_messages:
            # Keep recent messages
            self.messages = self.messages[-max_messages:]

    def get_token_estimate(self) -> int:
        """Estimate token count for conversation."""
        # Rough estimate: ~4 characters per token
        total_chars = len(self.system_prompt or "") + sum(
            len(m.content) for m in self.messages
        )
        return total_chars // 4