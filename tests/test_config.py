"""
Tests for KraberCode configuration module.
"""

from types import SimpleNamespace

import pytest

from krabercode.config.settings import ModelSettings, Settings, get_settings
from krabercode.config.storage import ConfigStorage
from krabercode.llm.client import LiteLLMClient
from krabercode.llm.messages import Message


class TestSettings:
    """Test settings configuration."""

    def test_default_settings(self):
        """Test default settings creation."""
        settings = Settings()
        assert settings.model.provider == "openai"
        assert settings.model.name == "gpt-4"
        assert settings.model.temperature == 0.7
        assert settings.model.stream is True

    def test_model_settings(self):
        """Test model-specific settings."""
        model = ModelSettings()
        assert model.provider == "openai"
        assert model.max_tokens == 4096

    def test_get_settings_singleton(self):
        """Test that get_settings returns a singleton."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2


class TestConfigStorage:
    """Test configuration storage."""

    def test_storage_creation(self, temp_dir):
        """Test creating config storage."""
        storage = ConfigStorage(config_dir=temp_dir)
        assert storage.config_dir == temp_dir
        assert storage.config_dir.exists()

    def test_save_and_load_config(self, temp_dir):
        """Test saving and loading config."""
        storage = ConfigStorage(config_dir=temp_dir)

        config = {"model": {"provider": "anthropic", "name": "claude"}}
        storage.save_config(config)

        loaded = storage.load_config()
        assert loaded["model"]["provider"] == "anthropic"

    def test_mcp_config(self, temp_dir):
        """Test MCP config handling."""
        storage = ConfigStorage(config_dir=temp_dir)

        mcp_config = {"servers": {"test": {"command": "test-server"}}}
        storage.save_mcp_config(mcp_config)

        loaded = storage.load_mcp_config()
        assert "servers" in loaded
        assert "test" in loaded["servers"]

    def test_history(self, temp_dir):
        """Test conversation history."""
        storage = ConfigStorage(config_dir=temp_dir)

        history = [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": "response"},
        ]
        storage.save_history(history)

        loaded = storage.load_history()
        assert len(loaded) == 2
        assert loaded[0]["role"] == "user"


class TestLLMTimeoutConfiguration:
    def test_configure_litellm_uses_provider_timeout(self, temp_dir, monkeypatch):
        import litellm

        settings = Settings()
        settings.model.provider = "openai"
        settings.openai.timeout = 123
        settings.tools.shell_timeout = 9

        storage = ConfigStorage(config_dir=temp_dir)

        monkeypatch.setattr(litellm, "request_timeout", None, raising=False)

        LiteLLMClient(settings=settings, storage=storage)

        assert litellm.request_timeout == 123


class TestLiteLLMStreamingAssembly:
    @pytest.mark.asyncio
    async def test_stream_emits_multiple_tool_calls(self, temp_dir, monkeypatch):
        class FakeStream:
            def __init__(self, chunks):
                self._chunks = chunks

            def __aiter__(self):
                self._iter = iter(self._chunks)
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration

        def chunk(*, tool_calls=None, finish_reason=None, prompt_tokens=10, completion_tokens=5):
            delta = SimpleNamespace(content=None, tool_calls=tool_calls)
            choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
            usage = SimpleNamespace(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            return SimpleNamespace(usage=usage, choices=[choice])

        tc0a = SimpleNamespace(
            id="call_0",
            index=0,
            function=SimpleNamespace(name="read_file", arguments='{"path":"a'),
        )
        tc1a = SimpleNamespace(
            id="call_1",
            index=1,
            function=SimpleNamespace(name="grep", arguments='{"pattern":"x'),
        )
        tc0b = SimpleNamespace(
            id=None,
            index=0,
            function=SimpleNamespace(name=None, arguments='"}'),
        )
        tc1b = SimpleNamespace(
            id=None,
            index=1,
            function=SimpleNamespace(name=None, arguments='"}'),
        )

        fake_chunks = [
            chunk(tool_calls=[tc0a, tc1a], finish_reason=None, completion_tokens=3),
            chunk(tool_calls=[tc0b, tc1b], finish_reason="tool_calls", completion_tokens=7),
            chunk(tool_calls=None, finish_reason="stop", completion_tokens=8),
        ]

        async def fake_acompletion(**kwargs):
            return FakeStream(fake_chunks)

        import litellm

        monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

        settings = Settings()
        settings.model.provider = "openai"
        settings.model.name = "gpt-4o"
        client = LiteLLMClient(settings=settings, storage=ConfigStorage(config_dir=temp_dir))

        tool_calls = []
        async for stream_chunk in client.stream([Message.user("run tools")], tools=[{"type": "function"}]):
            if stream_chunk.tool_call:
                tool_calls.append(stream_chunk.tool_call)

        assert len(tool_calls) == 2
        assert tool_calls[0].id == "call_0"
        assert tool_calls[0].name == "read_file"
        assert tool_calls[0].arguments == {"path": "a"}
        assert tool_calls[1].id == "call_1"
        assert tool_calls[1].name == "grep"
        assert tool_calls[1].arguments == {"pattern": "x"}


class TestMCPClientLifecycle:
    @pytest.mark.asyncio
    async def test_global_mcp_client_get_and_shutdown(self, monkeypatch):
        from krabercode.mcp import client as mcp_client

        class DummyMCPClient:
            async def initialize(self):
                return None

            async def shutdown(self):
                return None

        monkeypatch.setattr(mcp_client, "MCPClient", DummyMCPClient)
        monkeypatch.setattr(mcp_client, "_mcp_client", None)

        first = await mcp_client.get_mcp_client()
        second = await mcp_client.get_mcp_client()

        assert first is second

        await mcp_client.shutdown_mcp_client()
        assert mcp_client._mcp_client is None
