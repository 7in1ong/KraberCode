"""
Agent executor for KraberCode.

Main execution loop for handling user requests and tool calls.
"""

import asyncio
import json
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel

from krabercode.agent.context import ContextManager
from krabercode.agent.history import HistoryManager
from krabercode.agent.planner import TaskPlanner
from krabercode.agent.system_prompt import get_system_prompt
from krabercode.cli.output import OutputManager
from krabercode.config.settings import get_settings
from krabercode.config.storage import ConfigStorage
from krabercode.llm.client import get_llm_client
from krabercode.llm.messages import Message, MessageRole, ToolCall
from krabercode.tools.registry import get_tool_registry


class AgentExecutor:
    """Main agent executor for KraberCode."""
    
    MAX_ITERATIONS = 10
    
    def __init__(
        self,
        console: Optional[Console] = None,
        output: Optional[OutputManager] = None,
    ) -> None:
        """Initialize agent executor."""
        self.console = console or Console()
        self.output = output or OutputManager()
        self.settings = get_settings()
        self.storage = ConfigStorage()
        
        # Initialize components
        self.llm_client = get_llm_client()
        self.tool_registry = get_tool_registry()
        self.context = ContextManager()
        self.history = HistoryManager(self.storage.history_file)
        self.planner = TaskPlanner()
        
        # Set up system prompt
        self.context.set_system_prompt(get_system_prompt())
    
    async def execute(
        self,
        prompt: str,
        conversation: Optional[list[dict[str, str]]] = None,
    ) -> Optional[str]:
        """Execute a user prompt."""
        # Add user message to context
        self.context.add_message("user", prompt)
        
        # Track conversation if provided
        if conversation:
            self.context.conversation_history = [
                {"role": m["role"], "content": m["content"]}
                for m in conversation
            ]
        
        # Execute agent loop
        return await self._agent_loop(prompt)
    
    async def execute_single(self, prompt: str) -> None:
        """Execute a single prompt (non-interactive)."""
        response = await self.execute(prompt)
        
        if response:
            self.output.print_markdown(response)
    
    async def _agent_loop(self, initial_prompt: str) -> Optional[str]:
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
        messages = []
        
        # System prompt
        if self.context.system_prompt:
            messages.append(Message.system(self.context.system_prompt))
        
        # Conversation history
        for msg in self.context.conversation_history:
            role = MessageRole.USER if msg["role"] == "user" else MessageRole.ASSISTANT
            messages.append(Message(role=role, content=msg["content"]))
        
        return messages
    
    async def _stream_response(
        self,
        messages: list[Message],
        tools: list[dict],
    ) -> Optional[Any]:
        """Stream response from LLM."""
        from krabercode.llm.base import LLMResponse
        
        content_buffer = ""
        tool_calls: list[ToolCall] = []
        
        async for chunk in self.llm_client.stream(messages, tools):
            if chunk.content:
                content_buffer += chunk.content
                self.output.stream_response(chunk.content)
            
            if chunk.tool_call:
                tool_calls.append(chunk.tool_call)
        
        # Print newline after streaming
        self.console.print()
        
        # Get token counts from last chunk
        input_tokens = 0
        output_tokens = 0
        
        # Create response object
        response = LLMResponse(
            content=content_buffer,
            model=self.llm_client.model_name,
            provider=self.llm_client.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tool_calls=tool_calls,
        )
        
        if self.settings.output.show_tokens:
            self.output.print_token_usage(input_tokens, output_tokens)
        
        return response
    
    async def _complete_response(
        self,
        messages: list[Message],
        tools: list[dict],
    ) -> Optional[Any]:
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
            
            # Add tool result to context
            self.context.add_message(
                "tool",
                result.to_string(),
            )
            
            # Track tool call in history
            self.history.add_entry(
                "tool_call",
                json.dumps({"name": tool_name, "arguments": arguments}),
                {"result": result.success},
            )