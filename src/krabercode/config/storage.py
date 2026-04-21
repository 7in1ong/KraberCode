"""
Configuration storage and persistence for KraberCode.

Handles reading/writing config files, managing API keys securely,
base URLs for custom endpoints, and project-level configuration.
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
        """Path to the secrets file (API keys and base URLs)."""
        return self.config_dir / "secrets.yaml"

    @property
    def plan_file(self) -> Path:
        """Path to the coding plan file."""
        return self.config_dir / "plan.yaml"

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

    # === API Key Management ===

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider from secrets file."""
        # First check environment variables
        env_key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "alibaba": "DASHSCOPE_API_KEY",
            "google": "GOOGLE_API_KEY",
            "custom": "KRABER_CUSTOM_API_KEY",
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

        secrets.setdefault("providers", {})
        if provider not in secrets["providers"]:
            secrets["providers"][provider] = {}
        secrets["providers"][provider]["api_key"] = api_key

        with open(self.secrets_file, "w", encoding="utf-8") as f:
            yaml.dump(secrets, f, default_flow_style=False)

        # Set restrictive permissions on secrets file (Unix only)
        if os.name != "nt":
            os.chmod(self.secrets_file, 0o600)

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

    def list_api_keys_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all API keys (configured or from env)."""
        providers = ["openai", "anthropic", "alibaba", "google", "custom"]
        env_key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "alibaba": "DASHSCOPE_API_KEY",
            "google": "GOOGLE_API_KEY",
            "custom": "KRABER_CUSTOM_API_KEY",
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

    # === Base URL Management ===

    def get_base_url(self, provider: str) -> Optional[str]:
        """Get custom base URL for a provider."""
        # First check environment variable
        env_url_map = {
            "openai": "OPENAI_BASE_URL",
            "anthropic": "ANTHROPIC_BASE_URL",
            "custom": "KRABER_CUSTOM_BASE_URL",
        }
        env_var = env_url_map.get(provider)
        if env_var:
            url = os.environ.get(env_var)
            if url:
                return url

        # Then check secrets file
        if not self.secrets_file.exists():
            return None

        with open(self.secrets_file, encoding="utf-8") as f:
            secrets = yaml.safe_load(f) or {}
            return secrets.get("providers", {}).get(provider, {}).get("base_url")

    def set_base_url(self, provider: str, base_url: str) -> None:
        """Set custom base URL for a provider."""
        secrets: dict[str, Any] = {"providers": {}}

        if self.secrets_file.exists():
            with open(self.secrets_file, encoding="utf-8") as f:
                secrets = yaml.safe_load(f) or {"providers": {}}

        secrets.setdefault("providers", {})
        if provider not in secrets["providers"]:
            secrets["providers"][provider] = {}
        secrets["providers"][provider]["base_url"] = base_url

        with open(self.secrets_file, "w", encoding="utf-8") as f:
            yaml.dump(secrets, f, default_flow_style=False)

    def delete_base_url(self, provider: str) -> bool:
        """Delete custom base URL for a provider."""
        if not self.secrets_file.exists():
            return False

        with open(self.secrets_file, encoding="utf-8") as f:
            secrets = yaml.safe_load(f) or {}

        if provider in secrets.get("providers", {}):
            secrets["providers"][provider].pop("base_url", None)
            with open(self.secrets_file, "w", encoding="utf-8") as f:
                yaml.dump(secrets, f, default_flow_style=False)
            return True

        return False

    # === Coding Plan Management ===

    def load_plan(self) -> dict[str, Any]:
        """Load coding plan configuration."""
        if not self.plan_file.exists():
            return {}

        with open(self.plan_file, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_plan(self, plan: dict[str, Any]) -> None:
        """Save coding plan configuration."""
        with open(self.plan_file, "w", encoding="utf-8") as f:
            yaml.dump(plan, f, default_flow_style=False, allow_unicode=True)

    def get_active_plan(self) -> Optional[str]:
        """Get the name of the active coding plan."""
        plan = self.load_plan()
        return plan.get("active_plan")

    def set_active_plan(self, plan_name: str) -> None:
        """Set the active coding plan."""
        plan = self.load_plan()
        plan["active_plan"] = plan_name
        self.save_plan(plan)

    def list_plans(self) -> dict[str, dict[str, Any]]:
        """List all available coding plans."""
        plan = self.load_plan()
        return plan.get("plans", {})

    def get_plan_config(self, plan_name: str) -> Optional[dict[str, Any]]:
        """Get configuration for a specific plan."""
        plans = self.list_plans()
        return plans.get(plan_name)

    def create_plan(
        self,
        name: str,
        description: str = "",
        mode: str = "interactive",
        max_iterations: int = 10,
        auto_confirm: bool = False,
    ) -> None:
        """Create a new coding plan."""
        plan = self.load_plan()
        plan.setdefault("plans", {})
        plan["plans"][name] = {
            "description": description,
            "mode": mode,
            "max_iterations": max_iterations,
            "auto_confirm": auto_confirm,
        }
        self.save_plan(plan)

    def delete_plan(self, name: str) -> bool:
        """Delete a coding plan."""
        plan = self.load_plan()
        if name in plan.get("plans", {}):
            del plan["plans"][name]
            if plan.get("active_plan") == name:
                plan["active_plan"] = None
            self.save_plan(plan)
            return True
        return False

    def init_default_plan(self) -> None:
        """Initialize default coding plans."""
        if not self.plan_file.exists():
            default_plan = {
                "active_plan": "interactive",
                "plans": {
                    "interactive": {
                        "description": "Interactive mode - ask before each action",
                        "mode": "interactive",
                        "max_iterations": 10,
                        "auto_confirm": False,
                    },
                    "auto": {
                        "description": "Auto mode - execute with minimal prompts",
                        "mode": "auto",
                        "max_iterations": 20,
                        "auto_confirm": True,
                    },
                    "plan-first": {
                        "description": "Plan first - show plan before executing",
                        "mode": "plan-first",
                        "max_iterations": 15,
                        "auto_confirm": False,
                    },
                    "direct": {
                        "description": "Direct mode - single response without tools",
                        "mode": "direct",
                        "max_iterations": 1,
                        "auto_confirm": True,
                    },
                },
            }
            self.save_plan(default_plan)

    # === Project Config ===

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

    # === Default Config Initialization ===

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
                    "base_url": None,
                },
                "plan": {
                    "mode": "interactive",
                    "max_iterations": 10,
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
                        "base_url": "",
                        "_comment": "OpenAI API key and optional custom base URL",
                    },
                    "anthropic": {
                        "api_key": "",
                        "base_url": "",
                        "_comment": "Anthropic API key and optional custom base URL",
                    },
                    "alibaba": {
                        "api_key": "",
                        "_comment": "Dashscope API key (for Qwen models)",
                    },
                    "google": {
                        "api_key": "",
                        "_comment": "Google API key (for Gemini)",
                    },
                    "custom": {
                        "api_key": "",
                        "base_url": "",
                        "_comment": "Custom provider for OpenAI/Anthropic compatible APIs",
                    },
                },
                "_help": "API keys and base URLs can be set here or via environment variables.\n"
                         "Environment variables take priority:\n"
                         "  OPENAI_API_KEY, OPENAI_BASE_URL\n"
                         "  ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL\n"
                         "  KRABER_CUSTOM_API_KEY, KRABER_CUSTOM_BASE_URL",
            }
            with open(self.secrets_file, "w", encoding="utf-8") as f:
                yaml.dump(default_secrets, f, default_flow_style=False, allow_unicode=True)

        # Coding plan file
        self.init_default_plan()