"""Shared test fixtures and configuration."""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Dict, Any
from unittest.mock import MagicMock, AsyncMock

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# DIRECTORY FIXTURES
# ============================================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp(prefix="synod_test_"))
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_project(temp_dir: Path) -> Path:
    """Create a temporary project directory with .synod folder."""
    synod_dir = temp_dir / ".synod"
    synod_dir.mkdir()

    # Create basic project structure
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "main.py").write_text("print('hello')")
    (temp_dir / "README.md").write_text("# Test Project")

    return temp_dir


@pytest.fixture
def temp_home(temp_dir: Path, monkeypatch) -> Path:
    """Create a temporary home directory with .synod config."""
    home_synod = temp_dir / ".synod"
    home_synod.mkdir()

    # Mock home directory
    monkeypatch.setenv("HOME", str(temp_dir))
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    return temp_dir


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Return a mock configuration."""
    return {
        "api_key": "sk_test_12345",
        "api_url": "https://api.synod.run",
        "user_id": "test_user_123",
        "email": "test@example.com",
    }


@pytest.fixture
def mock_api_response() -> Dict[str, Any]:
    """Return a mock API response."""
    return {
        "status": "success",
        "debate_id": "debate_123",
        "bishops": ["claude", "gpt", "gemini"],
        "pope": "claude",
    }


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx async client."""
    import httpx

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    mock_response.text = '{"status": "success"}'
    mock_response.headers = {}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    return mock_client


# ============================================================================
# TOOL FIXTURES
# ============================================================================

@pytest.fixture
def sample_python_file(temp_dir: Path) -> Path:
    """Create a sample Python file for testing."""
    file_path = temp_dir / "sample.py"
    file_path.write_text('''"""Sample module for testing."""

def hello(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

class Calculator:
    """Simple calculator class."""

    def __init__(self):
        self.result = 0

    def add(self, x: int) -> int:
        self.result += x
        return self.result
''')
    return file_path


@pytest.fixture
def sample_json_file(temp_dir: Path) -> Path:
    """Create a sample JSON file for testing."""
    file_path = temp_dir / "config.json"
    data = {
        "name": "test",
        "version": "1.0.0",
        "settings": {
            "debug": True,
            "port": 8080,
        }
    }
    file_path.write_text(json.dumps(data, indent=2))
    return file_path


# ============================================================================
# HOOKS FIXTURES
# ============================================================================

@pytest.fixture
def hooks_config(temp_project: Path) -> Path:
    """Create a hooks configuration file."""
    hooks_file = temp_project / ".synod" / "hooks.json"
    hooks_data = {
        "hooks": [
            {
                "name": "test-hook",
                "event": "post_debate",
                "command": "echo 'hook executed'",
                "enabled": True,
            },
            {
                "name": "block-hook",
                "event": "pre_tool_use",
                "command": 'echo \'{"allow": false, "message": "blocked"}\'',
                "enabled": True,
            }
        ]
    }
    hooks_file.write_text(json.dumps(hooks_data, indent=2))
    return hooks_file


# ============================================================================
# CHECKPOINT FIXTURES
# ============================================================================

@pytest.fixture
def checkpoint_dir(temp_project: Path) -> Path:
    """Create a checkpoints directory."""
    cp_dir = temp_project / ".synod" / "checkpoints"
    cp_dir.mkdir(parents=True, exist_ok=True)
    return cp_dir


# ============================================================================
# SSE FIXTURES
# ============================================================================

@pytest.fixture
def mock_sse_events() -> list:
    """Return mock SSE events for debate simulation."""
    return [
        {"type": "classify_complete", "complexity": "moderate", "domains": ["python"]},
        {"type": "debate_start", "debate_id": "test_123", "bishops": ["claude", "gpt"]},
        {"type": "bishop_start", "bishop": "claude"},
        {"type": "bishop_token", "bishop": "claude", "token": "Here"},
        {"type": "bishop_token", "bishop": "claude", "token": " is"},
        {"type": "bishop_complete", "bishop": "claude", "tokens": 100},
        {"type": "pope_start"},
        {"type": "pope_token", "token": "The"},
        {"type": "pope_token", "token": " answer"},
        {"type": "pope_complete", "tokens": 50},
        {"type": "complete", "total_tokens": 150},
    ]


# ============================================================================
# CLEANUP
# ============================================================================

@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    yield

    # Reset hook manager
    try:
        from synod.core.hooks import _hook_manager
        import synod.core.hooks as hooks_module
        hooks_module._hook_manager = None
    except ImportError:
        pass

    # Reset checkpoint manager
    try:
        from synod.core.checkpoints import _checkpoint_manager
        import synod.core.checkpoints as cp_module
        cp_module._checkpoint_manager = None
    except ImportError:
        pass
