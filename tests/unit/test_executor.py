"""Unit tests for the tool executor."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from synod.tools.executor import (
    ToolExecutor,
    run_tool,
    reset_session_auto_approve,
    is_session_auto_approve,
    set_session_auto_approve,
)
from synod.tools.base import ToolStatus, ToolResult


# ============================================================================
# SESSION AUTO-APPROVE
# ============================================================================

class TestSessionAutoApprove:
    """Test session auto-approve functionality."""

    def test_default_is_false(self):
        """Test auto-approve is false by default."""
        reset_session_auto_approve()
        assert is_session_auto_approve() is False

    def test_set_auto_approve(self):
        """Test setting auto-approve."""
        reset_session_auto_approve()
        set_session_auto_approve(True)
        assert is_session_auto_approve() is True

    def test_reset_auto_approve(self):
        """Test resetting auto-approve."""
        set_session_auto_approve(True)
        reset_session_auto_approve()
        assert is_session_auto_approve() is False


# ============================================================================
# TOOL EXECUTOR INITIALIZATION
# ============================================================================

class TestExecutorInit:
    """Test ToolExecutor initialization."""

    def test_initialization(self, temp_dir):
        """Test basic initialization."""
        executor = ToolExecutor(str(temp_dir))
        assert executor.working_directory == str(temp_dir)
        assert len(executor.tools) > 0

    def test_default_tools_registered(self, temp_dir):
        """Test default tools are registered."""
        executor = ToolExecutor(str(temp_dir))

        assert "bash" in executor.tools
        assert "file_editor" in executor.tools
        assert "search" in executor.tools

    def test_get_tool(self, temp_dir):
        """Test getting a tool by name."""
        executor = ToolExecutor(str(temp_dir))

        tool = executor.get_tool("file_editor")
        assert tool is not None
        assert tool.name == "file_editor"

    def test_get_nonexistent_tool(self, temp_dir):
        """Test getting non-existent tool returns None."""
        executor = ToolExecutor(str(temp_dir))
        assert executor.get_tool("nonexistent") is None

    def test_get_all_tool_definitions(self, temp_dir):
        """Test getting all tool definitions."""
        executor = ToolExecutor(str(temp_dir))
        definitions = executor.get_all_tool_definitions()

        assert len(definitions) >= 3
        assert all("name" in d for d in definitions)


# ============================================================================
# TOOL EXECUTION
# ============================================================================

class TestToolExecution:
    """Test tool execution."""

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, temp_dir):
        """Test executing unknown tool returns error."""
        executor = ToolExecutor(str(temp_dir))
        result = await executor.execute("nonexistent_tool", {})

        assert result.status == ToolStatus.ERROR
        assert "unknown tool" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_file_view(self, temp_dir, sample_python_file):
        """Test executing file view operation."""
        executor = ToolExecutor(str(temp_dir))
        result = await executor.execute(
            "file_editor",
            {"operation": "view", "file_path": str(sample_python_file)},
            skip_confirmation=True,
        )

        assert result.status == ToolStatus.SUCCESS
        assert "def hello" in result.output

    @pytest.mark.asyncio
    async def test_execute_with_auto_approve(self, temp_dir):
        """Test execution with session auto-approve."""
        reset_session_auto_approve()
        set_session_auto_approve(True)

        executor = ToolExecutor(str(temp_dir))
        result = await executor.execute(
            "file_editor",
            {
                "operation": "create",
                "file_path": str(temp_dir / "auto_approved.py"),
                "content": "# auto approved",
            },
        )

        assert result.status == ToolStatus.SUCCESS
        reset_session_auto_approve()

    @pytest.mark.asyncio
    async def test_execute_with_skip_confirmation(self, temp_dir):
        """Test execution with skip_confirmation flag."""
        executor = ToolExecutor(str(temp_dir))
        result = await executor.execute(
            "file_editor",
            {
                "operation": "create",
                "file_path": str(temp_dir / "skipped.py"),
                "content": "# skipped confirmation",
            },
            skip_confirmation=True,
        )

        assert result.status == ToolStatus.SUCCESS


# ============================================================================
# HOOKS INTEGRATION
# ============================================================================

class TestHooksIntegration:
    """Test hooks integration in executor."""

    @pytest.mark.asyncio
    async def test_pre_tool_use_hook_called(self, temp_dir, sample_python_file):
        """Test pre_tool_use hook is called."""
        with patch('synod.tools.executor._get_hook_helpers') as mock_helpers:
            mock_run_hooks = MagicMock()
            mock_run_hooks.return_value = MagicMock(allow=True, modified_params=None)
            mock_helpers.return_value = (mock_run_hooks, MagicMock())

            executor = ToolExecutor(str(temp_dir))
            await executor.execute(
                "file_editor",
                {"operation": "view", "file_path": str(sample_python_file)},
                skip_confirmation=True,
            )

            # Verify pre_tool_use was called
            mock_run_hooks.assert_called()

    @pytest.mark.asyncio
    async def test_pre_tool_use_hook_can_block(self, temp_dir):
        """Test pre_tool_use hook can block execution."""
        with patch('synod.tools.executor._get_hook_helpers') as mock_helpers:
            mock_run_hooks = MagicMock()
            mock_run_hooks.return_value = MagicMock(
                allow=False,
                message="Blocked by test hook",
                modified_params=None,
            )

            from synod.core.hooks import HookEvent
            mock_helpers.return_value = (mock_run_hooks, HookEvent)

            executor = ToolExecutor(str(temp_dir))
            result = await executor.execute(
                "file_editor",
                {"operation": "view", "file_path": str(temp_dir / "test.py")},
                skip_confirmation=True,
            )

            assert result.status == ToolStatus.CANCELLED
            assert "blocked by hook" in result.error.lower()

    @pytest.mark.asyncio
    async def test_post_tool_use_hook_called(self, temp_dir, sample_python_file):
        """Test post_tool_use hook is called after execution."""
        call_count = 0

        def mock_run_hooks(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return MagicMock(allow=True, modified_params=None)

        with patch('synod.tools.executor._get_hook_helpers') as mock_helpers:
            from synod.core.hooks import HookEvent
            mock_helpers.return_value = (mock_run_hooks, HookEvent)

            executor = ToolExecutor(str(temp_dir))
            await executor.execute(
                "file_editor",
                {"operation": "view", "file_path": str(sample_python_file)},
                skip_confirmation=True,
            )

            # pre_tool_use + post_tool_use = at least 2 calls
            assert call_count >= 2


# ============================================================================
# CHECKPOINT INTEGRATION
# ============================================================================

class TestCheckpointIntegration:
    """Test checkpoint integration in executor."""

    @pytest.mark.asyncio
    async def test_checkpoint_created_before_file_modify(self, temp_dir):
        """Test checkpoint is created before file modification."""
        with patch('synod.tools.executor._get_checkpoint_helpers') as mock_cp:
            mock_create = MagicMock()
            mock_cp.return_value = mock_create

            executor = ToolExecutor(str(temp_dir))
            await executor.execute(
                "file_editor",
                {
                    "operation": "create",
                    "file_path": str(temp_dir / "checkpointed.py"),
                    "content": "# test",
                },
                skip_confirmation=True,
            )

            # Verify checkpoint was created
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_checkpoint_for_view(self, temp_dir, sample_python_file):
        """Test no checkpoint is created for view operations."""
        with patch('synod.tools.executor._get_checkpoint_helpers') as mock_cp:
            mock_create = MagicMock()
            mock_cp.return_value = mock_create

            executor = ToolExecutor(str(temp_dir))
            await executor.execute(
                "file_editor",
                {"operation": "view", "file_path": str(sample_python_file)},
                skip_confirmation=True,
            )

            # Verify checkpoint was NOT created
            mock_create.assert_not_called()


# ============================================================================
# HELPER METHODS
# ============================================================================

class TestHelperMethods:
    """Test executor helper methods."""

    def test_get_file_path_from_params_file_editor(self, temp_dir):
        """Test extracting file path from file_editor params."""
        executor = ToolExecutor(str(temp_dir))
        path = executor._get_file_path_from_params(
            "file_editor",
            {"operation": "create", "file_path": "/path/to/file.py"},
        )
        assert path == "/path/to/file.py"

    def test_get_file_path_from_params_bash(self, temp_dir):
        """Test extracting file path from bash params (returns None)."""
        executor = ToolExecutor(str(temp_dir))
        path = executor._get_file_path_from_params(
            "bash",
            {"command": "ls -la"},
        )
        assert path is None

    def test_is_modifying_operation_create(self, temp_dir):
        """Test create is a modifying operation."""
        executor = ToolExecutor(str(temp_dir))
        assert executor._is_modifying_operation(
            "file_editor",
            {"operation": "create"},
        ) is True

    def test_is_modifying_operation_str_replace(self, temp_dir):
        """Test str_replace is a modifying operation."""
        executor = ToolExecutor(str(temp_dir))
        assert executor._is_modifying_operation(
            "file_editor",
            {"operation": "str_replace"},
        ) is True

    def test_is_modifying_operation_view(self, temp_dir):
        """Test view is not a modifying operation."""
        executor = ToolExecutor(str(temp_dir))
        assert executor._is_modifying_operation(
            "file_editor",
            {"operation": "view"},
        ) is False

    def test_describe_action_file_editor(self, temp_dir):
        """Test action description for file_editor."""
        executor = ToolExecutor(str(temp_dir))
        desc = executor._describe_action(
            "file_editor",
            {"operation": "create", "file_path": "test.py"},
        )
        assert "create" in desc
        assert "test.py" in desc

    def test_describe_action_bash(self, temp_dir):
        """Test action description for bash."""
        executor = ToolExecutor(str(temp_dir))
        desc = executor._describe_action(
            "bash",
            {"command": "npm install"},
        )
        assert "bash" in desc
        assert "npm" in desc


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

class TestRunToolFunction:
    """Test run_tool convenience function."""

    @pytest.mark.asyncio
    async def test_run_tool(self, temp_dir, sample_python_file):
        """Test run_tool convenience function."""
        result = await run_tool(
            "file_editor",
            {"operation": "view", "file_path": str(sample_python_file)},
            str(temp_dir),
            skip_confirmation=True,
        )

        assert result.status == ToolStatus.SUCCESS


# ============================================================================
# WORKING DIRECTORY
# ============================================================================

class TestWorkingDirectory:
    """Test working directory management."""

    def test_get_working_directory(self, temp_dir):
        """Test getting working directory."""
        executor = ToolExecutor(str(temp_dir))
        assert executor.get_working_directory() == str(temp_dir)

    def test_update_working_directory(self, temp_dir):
        """Test updating working directory."""
        executor = ToolExecutor(str(temp_dir))
        new_dir = str(temp_dir / "subdir")

        executor.update_working_directory(new_dir)

        assert executor.working_directory == new_dir
        # All tools should have updated directory
        for tool in executor.tools.values():
            assert tool.working_directory == new_dir
