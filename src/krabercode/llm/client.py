"""
LLM client implementation using litellm.

Provides unified interface for multiple LLM providers.
"""

import asyncio
import json
from typing import Any, AsyncIterator, Optional

import litellm

from krabercode.config.settings import Settings, get_settings
from krabercode.config.storage import ConfigStorage
from krabercode.llm.base import LLMClient, LLMResponse, LLMStreamChunk, ToolDefinition
from krabercode.llm.messages import Message, ToolCall


class LiteLLMClient(LLMClient):
    """LLM client using litellm for unified provider support."""

    # Model name mapping for different providers
    MODEL_PREFIXES = {
        "openai": "openai/",
        "anthropic": "anthropic/",
        "alibaba": "dashscope/",  # Qwen models via Dashscope
        "google": "gemini/",
        "azure": "azure/",
    }

    def __init__(
        self,
        settings: Optional[Settings] = None,
        storage: Optional[ConfigStorage] = None,
    ) -> None:
        """Initialize the LLM client."""
        self.settings = settings or get_settings()
        self.storage = storage or ConfigStorage()
        self._configure_litellm()

    def _configure_litellm(self) -> None:
        """Configure litellm with API keys and settings."""
        # Set API keys from settings or storage
        openai_key = self.storage.get_api_key("openai") or self.settings.openai.api_key
        if openai_key:
            litellm.openai_key = openai_key

        anthropic_key = self.storage.get_api_key("anthropic") or self.settings.anthropic.api_key
        if anthropic_key:
            litellm.anthropic_key = anthropic_key

        alibaba_key = self.storage.get_api_key("alibaba") or self.settings.alibaba.api_key
        if alibaba_key:
            litellm.dashscope_key = alibaba_key

        google_key = self.storage.get_api_key("google") or self.settings.google.api_key
        if google_key:
            litellm.google_key = google_key

        # Configure defaults
        litellm.num_retries = 3
        litellm.retry_on_status_codes = [429, 500, 502, 503]

        # Enable caching (optional)
        litellm.cache = None  # Disable cache by default

        # Set timeout
        litellm.request_timeout = self.settings.tools.shell_timeout

    def _get_model_string(self) -> str:
        """Get the full model string for litellm."""
        provider = self.settings.model.provider
        model_name = self.settings.model.name

        # Check if model name already has prefix
        for prefix in self.MODEL_PREFIXES.values():
            if model_name.startswith(prefix):
                return model_name

        # Add prefix based on provider
        prefix = self.MODEL_PREFIXES.get(provider, "")
        return f"{prefix}{model_name}"

    async def complete(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send messages to LLM and get a complete response."""
        model = self._get_model_string()
        api_messages = [msg.to_openai_format() for msg in messages]

        # Merge kwargs with settings
        params = {
            "model": model,
            "messages": api_messages,
            "temperature": kwargs.get("temperature", self.settings.model.temperature),
            "max_tokens": kwargs.get("max_tokens", self.settings.model.max_tokens),
        }

        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        # Make the API call
        response = await litellm.acompletion(**params)

        # Parse response
        content = ""
        tool_calls: list[ToolCall] = []

        if response.choices:
            choice = response.choices[0]
            content = choice.message.content or ""

            # Parse tool calls
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    # Parse arguments from JSON string
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    tool_calls.append(
                        ToolCall(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=args,
                        )
                    )

        # Get token counts
        usage = response.usage or litellm.Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

        return LLMResponse(
            content=content,
            model=self.settings.model.name,
            provider=self.settings.model.provider,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason if response.choices else None,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream response from LLM."""
        model = self._get_model_string()
        api_messages = [msg.to_openai_format() for msg in messages]

        params = {
            "model": model,
            "messages": api_messages,
            "temperature": kwargs.get("temperature", self.settings.model.temperature),
            "max_tokens": kwargs.get("max_tokens", self.settings.model.max_tokens),
            "stream": True,
        }

        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        # Stream the response
        response = await litellm.acompletion(**params)

        # Track current tool call being built
        current_tool_call: Optional[dict[str, Any]] = None
        tool_arguments_buffer = ""

        input_tokens = 0
        output_tokens = 0

        async for chunk in response:
            # Update token counts if available
            if chunk.usage:
                input_tokens = chunk.usage.prompt_tokens
                output_tokens = chunk.usage.completion_tokens

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Handle content
            if delta.content:
                yield LLMStreamChunk(content=delta.content)

            # Handle tool calls (streaming)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    if tc_delta.id:
                        # New tool call
                        current_tool_call = {
                            "id": tc_delta.id,
                            "name": tc_delta.function.name if tc_delta.function else None,
                        }
                        tool_arguments_buffer = ""

                    if tc_delta.function and tc_delta.function.arguments:
                        # Accumulate arguments
                        tool_arguments_buffer += tc_delta.function.arguments

            # Check if tool call is complete
            if chunk.choices[0].finish_reason == "tool_calls":
                if current_tool_call and tool_arguments_buffer:
                    try:
                        args = json.loads(tool_arguments_buffer)
                    except json.JSONDecodeError:
                        args = {}

                    yield LLMStreamChunk(
                        tool_call=ToolCall(
                            id=current_tool_call["id"],
                            name=current_tool_call["name"] or "",
                            arguments=args,
                        ),
                        finish_reason="tool_calls",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )

            # Check for final chunk
            if chunk.choices[0].finish_reason:
                yield LLMStreamChunk(
                    finish_reason=chunk.choices[0].finish_reason,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

    async def count_tokens(self, messages: list[Message]) -> int:
        """Estimate token count for messages."""
        # Use litellm's token counter if available
        try:
            api_messages = [msg.to_openai_format() for msg in messages]
            return litellm.token_counter(
                model=self._get_model_string(),
                messages=api_messages,
            )
        except Exception:
            # Fallback to estimate
            total_chars = sum(len(m.content) for m in messages)
            return total_chars // 4

    @property
    def model_name(self) -> str:
        """Get the current model name."""
        return self.settings.model.name

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return self.settings.model.provider


# Global client instance (initialize before function definition)
_client: Optional[LiteLLMClient] = None


def get_llm_client() -> LiteLLMClient:
    """Get the global LLM client instance."""
    global _client
    if _client is None:
        _client = LiteLLMClient()
    return _client


def create_tool_definition(
    name: str,
    description: str,
    parameters: dict[str, Any],
    required: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create a tool definition in OpenAI format."""
    tool = ToolDefinition(
        name=name,
        description=description,
        parameters=parameters,
        required=required,
    )
    return tool.to_openai_format()