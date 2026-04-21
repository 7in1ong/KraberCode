"""
Agent executor for KraberCode.

Main execution loop for handling user requests and tool calls.
"""

import json
from typing import Any, Optional

from rich.console import Console

from krabercode.agent.context import ContextManager
from krabercode.agent.history import HistoryManager
from krabercode.agent.system_prompt import get_system_prompt
from krabercode.cli.output import OutputManager
from krabercode.config.settings import Settings, get_settings
from krabercode.config.storage import ConfigStorage
from krabercode.llm.base import LLMResponse
from krabercode.llm.client import LiteLLMClient, get_llm_client
from krabercode.llm.messages import Message, MessageRole, ToolCall
from krabercode.tools.base import ToolRegistry
from krabercode.tools.registry import get_tool_registry


class AgentExecutor:
    """Main agent executor for KraberCode."""

    MAX_ITERATIONS = 10

    def __init__(
        self,
        console: Optional[Console] = None,
        output: Optional[OutputManager] = None,
        settings: Optional[Settings] = None,
        storage: Optional[ConfigStorage] = None,
        llm_client: Optional[LiteLLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ) -> None:
        """Initialize agent executor."""
        self.console = console or Console()
        self.settings = settings or get_settings()
        self.output = output or OutputManager(console=self.console, settings=self.settings.output)
        self.storage = storage or ConfigStorage()

        # Initialize components
        self.llm_client = llm_client or get_llm_client()
        self.tool_registry = tool_registry or get_tool_registry()
        self.context = ContextManager()
        self.history = HistoryManager(self.storage.history_file)

        # Set up system prompt
        self.context.set_system_prompt(get_system_prompt())

    async def execute(
        self,
        prompt: str,
        conversation: Optional[list[dict[str, Any]]] = None,
    ) -> Optional[str]:
        """Execute a user prompt."""
        # Sync context from caller conversation first (if provided)
        if conversation is not None:
            self.context.conversation_history = [dict(m) for m in conversation]

        # Add current user message once
        should_add_user = True
        if conversation:
            last_msg = conversation[-1]
            should_add_user = not (
                last_msg.get("role") == "user" and last_msg.get("content") == prompt
            )

        if should_add_user:
            self.context.add_message("user", prompt)
            self.history.add_entry("user", prompt)

        # Execute agent loop
        return await self._agent_loop()

    async def execute_single(self, prompt: str) -> None:
        """Execute a single prompt (non-interactive)."""
        response = await self.execute(prompt)

        if response:
            self.output.print_markdown(response)

    async def _agent_loop(self) -> Optional[str]:
        """Main agent loop."""
        iteration = 0
        final_response: Optional[str] = None

        while iteration < self.MAX_ITERATIONS:
            iteration += 1

            # Get messages for LLM
            messages = self._build_messages()

            # Get tool definitions
            tools = self.tool_registry.get_all_definitions()

            # Call LLM
            self.console.print("[dim]Thinking...[/]")

            try:
                if self.settings.model.stream:
                    response = await self._stream_response(messages, tools)
                else:
                    response = await self._complete_response(messages, tools)

                if not response:
                    break

                # Check for tool calls
                if response.tool_calls:
                    # Add assistant tool-call message to context before tool execution
                    self.context.add_message(
                        "assistant",
                        response.content,
                        tool_calls=response.tool_calls,
                    )
                    self.history.add_entry(
                        "assistant",
                        response.content,
                        {"tool_calls": [tc.to_dict() for tc in response.tool_calls]},
                    )

                    self.console.print("[dim]Executing tools...[/]")
                    await self._execute_tools(response.tool_calls)
                    continue  # Loop back for more

                # Got final response
                final_response = response.content

                # Add assistant message
                self.context.add_message("assistant", final_response)

                # Save to history
                self.history.add_entry("assistant", final_response)

                break

            except Exception as e:
                self.output.print_error(f"LLM error: {e}")
                break

        return final_response

    def _build_messages(self) -> list[Message]:
        """Build messages for LLM."""
        messages: list[Message] = []

        # System prompt
        if self.context.system_prompt:
            messages.append(Message.system(self.context.system_prompt))

        # Conversation history
        for msg in self.context.conversation_history:
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                messages.append(Message.user(content))
            elif role == "assistant":
                tool_calls_data = msg.get("tool_calls") or []
                tool_calls: list[ToolCall] = []
                for tc in tool_calls_data:
                    if isinstance(tc, ToolCall):
                        tool_calls.append(tc)
                        continue

                    if not isinstance(tc, dict):
                        continue

                    function = tc.get("function", {})
                    arguments = function.get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {}

                    tool_calls.append(
                        ToolCall(
                            id=tc.get("id", ""),
                            name=function.get("name", ""),
                            arguments=arguments if isinstance(arguments, dict) else {},
                        )
                    )

                messages.append(Message.assistant(content, tool_calls=tool_calls))
            elif role == "tool":
                messages.append(
                    Message.tool_result(
                        content=content,
                        tool_call_id=msg.get("tool_call_id", ""),
                        tool_name=msg.get("name", "tool"),
                    )
                )
            elif role == "system":
                messages.append(Message.system(content))
            else:
                messages.append(Message(role=MessageRole.ASSISTANT, content=content))

        return messages

    async def _stream_response(
        self,
        messages: list[Message],
        tools: list[dict],
    ) -> Optional[LLMResponse]:
        """Stream response from LLM."""
        content_buffer = ""
        tool_calls: list[ToolCall] = []

        input_tokens = 0
        output_tokens = 0

        async for chunk in self.llm_client.stream(messages, tools):
            if chunk.content:
                content_buffer += chunk.content
                self.output.stream_response(chunk.content)

            if chunk.tool_call:
                tool_calls.append(chunk.tool_call)

            input_tokens = chunk.input_tokens or input_tokens
            output_tokens = chunk.output_tokens or output_tokens

        # Print newline after streaming
        self.console.print()

        # Create response object
        response = LLMResponse(
            content=content_buffer,
            model=self.llm_client.model_name,
            provider=self.llm_client.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            tool_calls=tool_calls,
        )

        if self.settings.output.show_tokens:
            self.output.print_token_usage(input_tokens, output_tokens)

        return response

    async def _complete_response(
        self,
        messages: list[Message],
        tools: list[dict],
    ) -> Optional[LLMResponse]:
        """Get complete response from LLM."""
        response = await self.llm_client.complete(messages, tools)

        # Display response
        if response.content:
            self.output.print_markdown(response.content)

        # Show token usage
        if self.settings.output.show_tokens:
            self.output.print_token_usage(
                response.input_tokens,
                response.output_tokens,
            )

        return response

    async def _execute_tools(self, tool_calls: list[ToolCall]) -> None:
        """Execute tool calls."""
        for tool_call in tool_calls:
            tool_name = tool_call.name
            arguments = tool_call.arguments

            # Display tool call
            self.output.print_tool_call(tool_name, arguments)

            # Execute tool
            result = await self.tool_registry.execute(tool_name, **arguments)

            # Display result
            self.output.print_tool_result(result.output, result.success)

            # Add tool result to context with tool_call_id
            self.context.add_message(
                "tool",
                result.to_string(),
                tool_call_id=tool_call.id,
                name=tool_name,
            )

            # Track tool call in history
            self.history.add_entry(
                "tool_call",
                json.dumps(
                    {
                        "id": tool_call.id,
                        "name": tool_name,
                        "arguments": arguments,
                    }
                ),
                {"result": result.success},
            )