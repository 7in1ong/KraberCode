"""
LLM client implementation using litellm.

Provides unified interface for multiple LLM providers with support for:
- OpenAI, Anthropic, Alibaba/Qwen, Google Gemini
- Custom Base URL for OpenAI/Anthropic compatible APIs
- Streaming and non-streaming responses
- Tool/function calling
"""

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
        "custom": "openai/",  # Custom providers use OpenAI protocol by default
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
        provider = self.settings.model.provider

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

        # Custom provider API key
        custom_key = self.storage.get_api_key("custom") or self.settings.custom.api_key
        if custom_key and provider == "custom":
            litellm.openai_key = custom_key  # Use OpenAI protocol

        # Configure defaults
        litellm.num_retries = 3
        litellm.retry_on_status_codes = [429, 500, 502, 503]

        # Enable caching (optional)
        litellm.cache = None  # Disable cache by default

        # Set timeout by provider/model settings (not tool shell timeout)
        provider_settings = getattr(self.settings, provider, None)
        provider_timeout = getattr(provider_settings, "timeout", None)
        litellm.request_timeout = provider_timeout or 60

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

    def _get_api_base_url(self) -> Optional[str]:
        """Get custom base URL if configured."""
        # Check storage first (user can set via /baseurl command)
        base_url = self.storage.get_base_url(self.settings.model.provider)

        # Then check settings
        if not base_url:
            base_url = self.settings.get_provider_base_url(self.settings.model.provider)

        return base_url

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

        # Add custom base URL if configured
        base_url = self._get_api_base_url()
        if base_url:
            params["api_base"] = base_url

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

        # Add custom base URL if configured
        base_url = self._get_api_base_url()
        if base_url:
            params["api_base"] = base_url

        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        # Stream the response
        response = await litellm.acompletion(**params)

        # Track tool call fragments by index
        tool_call_fragments: dict[int, dict[str, Any]] = {}

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
                    idx = getattr(tc_delta, "index", 0)

                    fragment = tool_call_fragments.setdefault(
                        idx,
                        {"id": "", "name": "", "arguments": ""},
                    )

                    if tc_delta.id:
                        fragment["id"] = tc_delta.id

                    if tc_delta.function:
                        if tc_delta.function.name:
                            fragment["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            fragment["arguments"] += tc_delta.function.arguments

            # Emit all completed tool calls when tool-calls turn ends
            if chunk.choices[0].finish_reason == "tool_calls":
                for idx in sorted(tool_call_fragments.keys()):
                    fragment = tool_call_fragments[idx]
                    try:
                        args = json.loads(fragment["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}

                    yield LLMStreamChunk(
                        tool_call=ToolCall(
                            id=fragment["id"],
                            name=fragment["name"],
                            arguments=args,
                        ),
                        finish_reason="tool_calls",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )

                tool_call_fragments.clear()

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