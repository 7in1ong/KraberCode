"""
KraberCode configuration settings.

Uses pydantic-settings for type-safe configuration management
with environment variable and file support.
"""

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelSettings(BaseSettings):
    """Model-specific configuration."""

    model_config = SettingsConfigDict(env_prefix="KRABER_MODEL_")

    provider: Literal["openai", "anthropic", "google", "alibaba", "azure", "custom"] = Field(
        default="openai",
        description="LLM provider to use",
    )
    name: str = Field(
        default="gpt-4",
        description="Model name/identifier",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for model responses",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        description="Maximum tokens in response",
    )
    stream: bool = Field(
        default=True,
        description="Enable streaming responses",
    )


class ProviderSettings(BaseSettings):
    """Provider-specific API configuration."""

    api_key: Optional[str] = Field(default=None, description="API key for the provider")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    timeout: int = Field(default=60, ge=1, description="Request timeout in seconds")


class OpenAIProviderSettings(ProviderSettings):
    """OpenAI-specific settings."""

    model_config = SettingsConfigDict(env_prefix="KRABER_OPENAI_")

    api_key: Optional[str] = Field(
        default=None,
        alias="openai_api_key",
        description="OpenAI API key",
    )
    organization: Optional[str] = Field(default=None, description="OpenAI organization ID")


class AnthropicProviderSettings(ProviderSettings):
    """Anthropic-specific settings."""

    model_config = SettingsConfigDict(env_prefix="KRABER_ANTHROPIC_")

    api_key: Optional[str] = Field(
        default=None,
        alias="anthropic_api_key",
        description="Anthropic API key",
    )


class AlibabaProviderSettings(ProviderSettings):
    """Alibaba/Qwen-specific settings."""

    model_config = SettingsConfigDict(env_prefix="KRABER_ALIBABA_")

    api_key: Optional[str] = Field(
        default=None,
        alias="dashscope_api_key",
        description="Dashscope API key for Alibaba models",
    )


class GoogleProviderSettings(ProviderSettings):
    """Google Gemini-specific settings."""

    model_config = SettingsConfigDict(env_prefix="KRABER_GOOGLE_")

    api_key: Optional[str] = Field(
        default=None,
        alias="google_api_key",
        description="Google API key",
    )


class MCPSettings(BaseSettings):
    """MCP (Model Context Protocol) settings."""

    model_config = SettingsConfigDict(env_prefix="KRABER_MCP_")

    enabled: bool = Field(default=True, description="Enable MCP integration")
    config_path: Optional[Path] = Field(
        default=None,
        description="Path to MCP servers configuration file",
    )
    timeout: int = Field(default=30, ge=1, description="MCP server connection timeout")


class ToolSettings(BaseSettings):
    """Tool execution settings."""

    model_config = SettingsConfigDict(env_prefix="KRABER_TOOL_")

    shell_timeout: int = Field(
        default=120,
        ge=1,
        description="Timeout for shell command execution (seconds)",
    )
    max_file_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum file size to read (bytes)",
    )
    allowed_commands: list[str] = Field(
        default_factory=list,
        description="List of allowed shell commands (empty = all allowed)",
    )
    sandbox_enabled: bool = Field(
        default=False,
        description="Enable sandboxed command execution",
    )


class OutputSettings(BaseSettings):
    """Output/display settings."""

    model_config = SettingsConfigDict(env_prefix="KRABER_OUTPUT_")

    format: Literal["text", "markdown", "json"] = Field(
        default="markdown",
        description="Output format",
    )
    color: bool = Field(
        default=True,
        description="Enable colored output",
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose output",
    )
    show_tokens: bool = Field(
        default=True,
        description="Show token usage statistics",
    )


class Settings(BaseSettings):
    """Main KraberCode settings."""

    model_config = SettingsConfigDict(
        env_prefix="KRABER_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # Core settings
    debug: bool = Field(default=False, description="Enable debug mode")

    # Nested settings
    model: ModelSettings = Field(default_factory=ModelSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)

    # Provider settings
    openai: OpenAIProviderSettings = Field(default_factory=OpenAIProviderSettings)
    anthropic: AnthropicProviderSettings = Field(default_factory=AnthropicProviderSettings)
    alibaba: AlibabaProviderSettings = Field(default_factory=AlibabaProviderSettings)
    google: GoogleProviderSettings = Field(default_factory=GoogleProviderSettings)

    # Paths
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / ".krabercode",
        description="Configuration directory",
    )

    def get_provider_api_key(self, provider: str) -> Optional[str]:
        """Get the API key for a specific provider."""
        provider_map = {
            "openai": self.openai.api_key,
            "anthropic": self.anthropic.api_key,
            "alibaba": self.alibaba.api_key,
            "google": self.google.api_key,
        }
        return provider_map.get(provider)


# Global settings instance (initialize before function definition)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment and config files."""
    global _settings
    _settings = Settings()
    return _settings