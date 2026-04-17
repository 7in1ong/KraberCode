"""
Configuration storage and persistence for KraberCode.

Handles reading/writing config files, managing API keys securely,
and project-level configuration.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

import yaml

from krabercode.config.settings import Settings, get_settings


class ConfigStorage:
    """Manages configuration file storage and retrieval."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize storage with optional custom config directory."""
        self.settings = get_settings()
        self.config_dir = config_dir or self.settings.config_dir
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    @property
    def config_file(self) -> Path:
        """Path to the main config file."""
        return self.config_dir / "config.yaml"

    @property
    def mcp_config_file(self) -> Path:
        """Path to the MCP configuration file."""
        return self.config_dir / "mcp.yaml"

    @property
    def history_file(self) -> Path:
        """Path to the conversation history file."""
        return self.config_dir / "history.json"

    @property
    def secrets_file(self) -> Path:
        """Path to the secrets file (API keys)."""
        return self.config_dir / "secrets.yaml"

    def load_config(self) -> dict[str, Any]:
        """Load configuration from file."""
        if not self.config_file.exists():
            return {}

        with open(self.config_file, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_config(self, config: dict[str, Any]) -> None:
        """Save configuration to file."""
        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    def load_mcp_config(self) -> dict[str, Any]:
        """Load MCP server configuration."""
        if not self.mcp_config_file.exists():
            return {"servers": {}}

        with open(self.mcp_config_file, encoding="utf-8") as f:
            return yaml.safe_load(f) or {"servers": {}}

    def save_mcp_config(self, config: dict[str, Any]) -> None:
        """Save MCP server configuration."""
        with open(self.mcp_config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    def load_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Load conversation history."""
        if not self.history_file.exists():
            return []

        with open(self.history_file, encoding="utf-8") as f:
            history = json.load(f)
            return history[-limit:] if len(history) > limit else history

    def save_history(self, history: list[dict[str, Any]]) -> None:
        """Save conversation history."""
        # Limit history to prevent file from growing too large
        max_entries = 1000
        if len(history) > max_entries:
            history = history[-max_entries:]

        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider from secrets file."""
        # First check environment variables
        env_key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "alibaba": "DASHSCOPE_API_KEY",
            "google": "GOOGLE_API_KEY",
        }

        env_var = env_key_map.get(provider)
        if env_var:
            key = os.environ.get(env_var)
            if key:
                return key

        # Then check secrets file
        if not self.secrets_file.exists():
            return None

        with open(self.secrets_file, encoding="utf-8") as f:
            secrets = yaml.safe_load(f) or {}
            return secrets.get("providers", {}).get(provider, {}).get("api_key")

    def set_api_key(self, provider: str, api_key: str) -> None:
        """Save API key for a provider to secrets file."""
        secrets: dict[str, Any] = {"providers": {}}

        if self.secrets_file.exists():
            with open(self.secrets_file, encoding="utf-8") as f:
                secrets = yaml.safe_load(f) or {"providers": {}}

        secrets.setdefault("providers", {})[provider] = {"api_key": api_key}

        with open(self.secrets_file, "w", encoding="utf-8") as f:
            yaml.dump(secrets, f, default_flow_style=False)

        # Set restrictive permissions on secrets file (Unix only)
        if os.name != "nt":
            os.chmod(self.secrets_file, 0o600)

    def get_project_config_path(self, project_root: Path) -> Path:
        """Get project-level configuration path."""
        return project_root / ".krabercode" / "config.yaml"

    def load_project_config(self, project_root: Path) -> dict[str, Any]:
        """Load project-level configuration."""
        config_path = self.get_project_config_path(project_root)
        if not config_path.exists():
            return {}

        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_project_config(self, project_root: Path, config: dict[str, Any]) -> None:
        """Save project-level configuration."""
        config_path = self.get_project_config_path(project_root)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    def init_default_config(self) -> None:
        """Initialize default configuration files with templates."""
        # Main config file
        if not self.config_file.exists():
            default_config = {
                "model": {
                    "provider": "openai",
                    "name": "gpt-4o",
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "stream": True,
                },
                "output": {
                    "format": "markdown",
                    "color": True,
                    "verbose": False,
                    "show_tokens": True,
                },
                "tools": {
                    "shell_timeout": 120,
                    "max_file_size": 10485760,  # 10MB
                },
            }
            self.save_config(default_config)

        # MCP config file
        if not self.mcp_config_file.exists():
            default_mcp = {
                "servers": {},
                "_help": "Add MCP servers here. Example:\n# servers:\n#   filesystem:\n#     command: mcp-server-filesystem\n#     args: ['--path', '/path/to/project']",
            }
            self.save_mcp_config(default_mcp)

        # Secrets/API keys file with template
        if not self.secrets_file.exists():
            default_secrets = {
                "providers": {
                    "openai": {
                        "api_key": "",
                        "_comment": "Set your OpenAI API key here or use OPENAI_API_KEY env var",
                    },
                    "anthropic": {
                        "api_key": "",
                        "_comment": "Set your Anthropic API key here or use ANTHROPIC_API_KEY env var",
                    },
                    "alibaba": {
                        "api_key": "",
                        "_comment": "Set your Dashscope API key (for Qwen models) or use DASHSCOPE_API_KEY env var",
                    },
                    "google": {
                        "api_key": "",
                        "_comment": "Set your Google API key (for Gemini) or use GOOGLE_API_KEY env var",
                    },
                },
                "_help": "API keys can be set here or via environment variables. Environment variables take priority.",
            }
            with open(self.secrets_file, "w", encoding="utf-8") as f:
                yaml.dump(default_secrets, f, default_flow_style=False, allow_unicode=True)

    def list_api_keys_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all API keys (configured or from env)."""
        providers = ["openai", "anthropic", "alibaba", "google"]
        env_key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "alibaba": "DASHSCOPE_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        
        status = {}
        for provider in providers:
            env_var = env_key_map[provider]
            env_key = os.environ.get(env_var)
            file_key = None
            
            if self.secrets_file.exists():
                with open(self.secrets_file, encoding="utf-8") as f:
                    secrets = yaml.safe_load(f) or {}
                    file_key = secrets.get("providers", {}).get(provider, {}).get("api_key")
            
            # Check if key is set (non-empty)
            has_key = bool(env_key or (file_key and file_key.strip()))
            source = "env" if env_key else ("file" if file_key and file_key.strip() else "none")
            
            status[provider] = {
                "has_key": has_key,
                "source": source,
                "env_var": env_var,
            }
        
        return status
    
    def delete_api_key(self, provider: str) -> bool:
        """Delete API key for a provider from secrets file."""
        if not self.secrets_file.exists():
            return False
        
        with open(self.secrets_file, encoding="utf-8") as f:
            secrets = yaml.safe_load(f) or {}
        
        if provider in secrets.get("providers", {}):
            secrets["providers"][provider]["api_key"] = ""
            with open(self.secrets_file, "w", encoding="utf-8") as f:
                yaml.dump(secrets, f, default_flow_style=False)
            return True
        
        return False