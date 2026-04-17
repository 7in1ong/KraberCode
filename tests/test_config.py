"""
Tests for KraberCode configuration module.
"""

import pytest
from pathlib import Path
import tempfile

from krabercode.config.settings import Settings, ModelSettings, get_settings
from krabercode.config.storage import ConfigStorage


class TestSettings:
    """Test settings configuration."""
    
    def test_default_settings(self):
        """Test default settings creation."""
        settings = Settings()
        assert settings.model.provider == "openai"
        assert settings.model.name == "gpt-4"
        assert settings.model.temperature == 0.7
        assert settings.model.stream == True
    
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