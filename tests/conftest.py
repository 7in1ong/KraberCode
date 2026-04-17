"""
Test configuration for KraberCode.

Provides fixtures and configuration for pytest.
"""

import pytest
from pathlib import Path
import tempfile


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_file(temp_dir):
    """Create a temporary file for tests."""
    file_path = temp_dir / "test_file.txt"
    file_path.write_text("test content")
    yield file_path


@pytest.fixture
def mock_settings():
    """Create mock settings for tests."""
    from krabercode.config.settings import Settings
    settings = Settings()
    settings.model.provider = "openai"
    settings.model.name = "gpt-4"
    settings.model.temperature = 0.7
    settings.debug = False
    return settings