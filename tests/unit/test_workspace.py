"""Unit tests for the workspace module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from synod.core.workspace import (
    load_trusted_workspaces,
    save_trusted_workspace,
    is_workspace_trusted,
    check_workspace_trust,
)


# ============================================================================
# LOAD TRUSTED WORKSPACES
# ============================================================================

class TestLoadTrustedWorkspaces:
    """Test load_trusted_workspaces function."""

    def test_load_nonexistent_file(self, temp_dir):
        """Test loading when file doesn't exist."""
        with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(temp_dir / "nonexistent.json")):
            trusted = load_trusted_workspaces()
            assert trusted == set()

    def test_load_existing_file(self, temp_dir):
        """Test loading from existing file."""
        trusted_file = temp_dir / "trusted.json"
        trusted_file.write_text(json.dumps({
            "trusted_paths": ["/path/to/project1", "/path/to/project2"]
        }))

        with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
            trusted = load_trusted_workspaces()
            assert trusted == {"/path/to/project1", "/path/to/project2"}

    def test_load_invalid_json(self, temp_dir):
        """Test loading invalid JSON returns empty set."""
        trusted_file = temp_dir / "invalid.json"
        trusted_file.write_text("not valid json")

        with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
            trusted = load_trusted_workspaces()
            assert trusted == set()

    def test_load_empty_file(self, temp_dir):
        """Test loading empty paths list."""
        trusted_file = temp_dir / "empty.json"
        trusted_file.write_text(json.dumps({"trusted_paths": []}))

        with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
            trusted = load_trusted_workspaces()
            assert trusted == set()


# ============================================================================
# SAVE TRUSTED WORKSPACE
# ============================================================================

class TestSaveTrustedWorkspace:
    """Test save_trusted_workspace function."""

    def test_save_new_workspace(self, temp_dir):
        """Test saving a new trusted workspace."""
        config_dir = temp_dir / "config"
        trusted_file = config_dir / "trusted.json"

        with patch('synod.core.workspace.CONFIG_DIR', str(config_dir)):
            with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
                save_trusted_workspace("/new/project")

                # File should be created
                assert trusted_file.exists()

                data = json.loads(trusted_file.read_text())
                # Path should be resolved
                assert any("/new/project" in p or "new/project" in p for p in data["trusted_paths"])

    def test_save_adds_to_existing(self, temp_dir):
        """Test saving adds to existing workspaces."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()
        trusted_file = config_dir / "trusted.json"
        trusted_file.write_text(json.dumps({
            "trusted_paths": ["/existing/project"]
        }))

        with patch('synod.core.workspace.CONFIG_DIR', str(config_dir)):
            with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
                save_trusted_workspace(str(temp_dir))

                data = json.loads(trusted_file.read_text())
                assert "/existing/project" in data["trusted_paths"]
                # New path should also be present (resolved)
                assert len(data["trusted_paths"]) >= 2


# ============================================================================
# IS WORKSPACE TRUSTED
# ============================================================================

class TestIsWorkspaceTrusted:
    """Test is_workspace_trusted function."""

    def test_trusted_workspace(self, temp_dir):
        """Test checking a trusted workspace."""
        trusted_file = temp_dir / "trusted.json"
        # Save with resolved path
        resolved = str(temp_dir.resolve())
        trusted_file.write_text(json.dumps({
            "trusted_paths": [resolved]
        }))

        with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
            assert is_workspace_trusted(str(temp_dir)) is True

    def test_untrusted_workspace(self, temp_dir):
        """Test checking an untrusted workspace."""
        trusted_file = temp_dir / "trusted.json"
        trusted_file.write_text(json.dumps({
            "trusted_paths": ["/other/project"]
        }))

        with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
            assert is_workspace_trusted("/untrusted/path") is False

    def test_empty_trusted_list(self, temp_dir):
        """Test checking when no workspaces trusted."""
        trusted_file = temp_dir / "trusted.json"
        trusted_file.write_text(json.dumps({"trusted_paths": []}))

        with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
            assert is_workspace_trusted("/any/path") is False


# ============================================================================
# CHECK WORKSPACE TRUST
# ============================================================================

class TestCheckWorkspaceTrust:
    """Test check_workspace_trust function."""

    @pytest.mark.asyncio
    async def test_already_trusted_workspace(self, temp_dir):
        """Test check returns True for already trusted workspace."""
        trusted_file = temp_dir / "trusted.json"
        resolved = str(temp_dir.resolve())
        trusted_file.write_text(json.dumps({
            "trusted_paths": [resolved]
        }))

        with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
            result = await check_workspace_trust(str(temp_dir))
            assert result is True

    @pytest.mark.asyncio
    async def test_prompts_for_untrusted(self, temp_dir):
        """Test check prompts user for untrusted workspace."""
        trusted_file = temp_dir / "trusted.json"
        trusted_file.write_text(json.dumps({"trusted_paths": []}))

        # Mock the prompt function to return True (user trusts)
        with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
            with patch('synod.core.workspace.is_workspace_trusted', return_value=False):
                with patch('synod.core.workspace.prompt_workspace_trust', new_callable=AsyncMock) as mock_prompt:
                    mock_prompt.return_value = True

                    result = await check_workspace_trust("/untrusted/path")

                    assert result is True
                    mock_prompt.assert_called_once_with("/untrusted/path")

    @pytest.mark.asyncio
    async def test_returns_false_when_user_denies(self, temp_dir):
        """Test check returns False when user denies trust."""
        trusted_file = temp_dir / "trusted.json"
        trusted_file.write_text(json.dumps({"trusted_paths": []}))

        with patch('synod.core.workspace.TRUSTED_WORKSPACES_FILE', str(trusted_file)):
            with patch('synod.core.workspace.is_workspace_trusted', return_value=False):
                with patch('synod.core.workspace.prompt_workspace_trust', new_callable=AsyncMock) as mock_prompt:
                    mock_prompt.return_value = False

                    result = await check_workspace_trust("/untrusted/path")

                    assert result is False
