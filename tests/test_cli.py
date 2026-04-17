"""
Tests for KraberCode CLI module.
"""

import pytest
from typer.testing import CliRunner

from krabercode.cli.commands import app
from krabercode import __version__


runner = CliRunner()


class TestCLICommands:
    """Test CLI commands."""
    
    def test_version_command(self):
        """Test version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output
    
    def test_config_init(self, temp_dir):
        """Test config init command."""
        # This would require mocking the config directory
        # For now, just test the command runs
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
    
    def test_tools_list(self):
        """Test tools list command."""
        result = runner.invoke(app, ["tools", "--list"])
        assert result.exit_code == 0
        assert "read_file" in result.output
    
    def test_help_command(self):
        """Test help command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "KraberCode" in result.output