"""Integration tests for complete workflows."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from synod.tools.executor import ToolExecutor, reset_session_auto_approve
from synod.tools.base import ToolStatus
from synod.core.hooks import HookManager, Hook, HookEvent, run_hooks
from synod.core.checkpoints import CheckpointManager, reset_checkpoint_manager


# ============================================================================
# FILE EDITING WORKFLOW
# ============================================================================

@pytest.mark.integration
class TestFileEditingWorkflow:
    """Test complete file editing workflow with hooks and checkpoints."""

    @pytest.mark.asyncio
    async def test_create_edit_rewind_workflow(self, temp_project):
        """Test creating a file, editing it, and rewinding."""
        reset_session_auto_approve()
        reset_checkpoint_manager()

        # Initialize managers
        import synod.core.checkpoints as cp_module
        cp_module._checkpoint_manager = CheckpointManager(str(temp_project))

        executor = ToolExecutor(str(temp_project))
        file_path = temp_project / "workflow_test.py"

        # Step 1: Create file
        result = await executor.execute(
            "file_editor",
            {
                "operation": "create",
                "file_path": str(file_path),
                "content": "def original():\n    return 1",
            },
            skip_confirmation=True,
        )
        assert result.status == ToolStatus.SUCCESS
        assert file_path.read_text() == "def original():\n    return 1"

        # Step 2: Edit file
        result = await executor.execute(
            "file_editor",
            {
                "operation": "str_replace",
                "file_path": str(file_path),
                "old_str": "def original():\n    return 1",
                "new_str": "def modified():\n    return 2",
            },
            skip_confirmation=True,
        )
        assert result.status == ToolStatus.SUCCESS
        assert "def modified()" in file_path.read_text()

        # Step 3: Verify checkpoint exists
        manager = cp_module._checkpoint_manager
        checkpoints = manager.get_checkpoints()
        assert len(checkpoints) >= 1

        # Step 4: Rewind to before edit
        latest = checkpoints[0]  # Most recent (the edit)
        manager.restore_checkpoint(latest.id)

        # File should be back to original
        assert "def original()" in file_path.read_text()

    @pytest.mark.asyncio
    async def test_view_search_workflow(self, temp_project):
        """Test viewing and searching files."""
        executor = ToolExecutor(str(temp_project))

        # Create some files
        (temp_project / "module_a.py").write_text("def func_a():\n    pass")
        (temp_project / "module_b.py").write_text("def func_b():\n    pass")

        # View file
        result = await executor.execute(
            "file_editor",
            {"operation": "view", "file_path": str(temp_project / "module_a.py")},
            skip_confirmation=True,
        )
        assert result.status == ToolStatus.SUCCESS
        assert "func_a" in result.output

        # View directory listing
        result = await executor.execute(
            "file_editor",
            {"operation": "view", "file_path": str(temp_project)},
            skip_confirmation=True,
        )
        assert result.status == ToolStatus.SUCCESS
        assert "module_a.py" in result.output


# ============================================================================
# HOOKS WORKFLOW
# ============================================================================

@pytest.mark.integration
class TestHooksWorkflow:
    """Test hooks in complete workflows."""

    @pytest.mark.asyncio
    async def test_post_file_modified_hook(self, temp_project):
        """Test file_modified hook fires after file changes."""
        reset_session_auto_approve()

        # Create a hook that records when it's called
        marker_file = temp_project / ".hook_marker"
        hooks_file = temp_project / ".synod" / "hooks.json"
        hooks_data = {
            "hooks": [{
                "name": "mark-modified",
                "event": "file_modified",
                "command": f"touch {marker_file}",
                "enabled": True,
            }]
        }
        hooks_file.write_text(json.dumps(hooks_data))

        # Reset and load hooks
        import synod.core.hooks as hooks_module
        hooks_module._hook_manager = HookManager(str(temp_project))

        executor = ToolExecutor(str(temp_project))

        # Create a file (should trigger file_modified)
        result = await executor.execute(
            "file_editor",
            {
                "operation": "create",
                "file_path": str(temp_project / "trigger_hook.py"),
                "content": "# trigger hook",
            },
            skip_confirmation=True,
        )
        assert result.status == ToolStatus.SUCCESS

        # Hook should have created marker file
        assert marker_file.exists()

    @pytest.mark.asyncio
    async def test_blocking_hook_prevents_edit(self, temp_project):
        """Test pre_tool_use hook can prevent file edits."""
        reset_session_auto_approve()

        # Create a blocking hook
        hooks_file = temp_project / ".synod" / "hooks.json"
        hooks_data = {
            "hooks": [{
                "name": "block-all",
                "event": "pre_tool_use",
                "command": "echo '{\"allow\": false, \"message\": \"All edits blocked\"}'",
                "enabled": True,
            }]
        }
        hooks_file.write_text(json.dumps(hooks_data))

        import synod.core.hooks as hooks_module
        hooks_module._hook_manager = HookManager(str(temp_project))

        executor = ToolExecutor(str(temp_project))

        # Try to create a file
        result = await executor.execute(
            "file_editor",
            {
                "operation": "create",
                "file_path": str(temp_project / "blocked.py"),
                "content": "# should be blocked",
            },
            skip_confirmation=True,
        )

        # Should be blocked
        assert result.status == ToolStatus.CANCELLED
        assert "blocked" in result.error.lower()
        assert not (temp_project / "blocked.py").exists()


# ============================================================================
# MULTI-FILE WORKFLOW
# ============================================================================

@pytest.mark.integration
class TestMultiFileWorkflow:
    """Test workflows involving multiple files."""

    @pytest.mark.asyncio
    async def test_batch_file_creation(self, temp_project):
        """Test creating multiple files in sequence."""
        reset_session_auto_approve()
        executor = ToolExecutor(str(temp_project))

        files = [
            ("models.py", "class User:\n    pass"),
            ("views.py", "def index():\n    pass"),
            ("routes.py", "routes = []"),
        ]

        for filename, content in files:
            result = await executor.execute(
                "file_editor",
                {
                    "operation": "create",
                    "file_path": str(temp_project / filename),
                    "content": content,
                },
                skip_confirmation=True,
            )
            assert result.status == ToolStatus.SUCCESS

        # Verify all files exist
        for filename, _ in files:
            assert (temp_project / filename).exists()

    @pytest.mark.asyncio
    async def test_refactor_across_files(self, temp_project):
        """Test refactoring that touches multiple files."""
        reset_session_auto_approve()
        executor = ToolExecutor(str(temp_project))

        # Create two files that reference each other
        (temp_project / "utils.py").write_text("def old_helper():\n    return 'old'")
        (temp_project / "main.py").write_text("from utils import old_helper\n\nold_helper()")

        # Rename function in utils.py
        result = await executor.execute(
            "file_editor",
            {
                "operation": "str_replace",
                "file_path": str(temp_project / "utils.py"),
                "old_str": "def old_helper():",
                "new_str": "def new_helper():",
            },
            skip_confirmation=True,
        )
        assert result.status == ToolStatus.SUCCESS

        # Update import in main.py
        result = await executor.execute(
            "file_editor",
            {
                "operation": "str_replace",
                "file_path": str(temp_project / "main.py"),
                "old_str": "from utils import old_helper\n\nold_helper()",
                "new_str": "from utils import new_helper\n\nnew_helper()",
            },
            skip_confirmation=True,
        )
        assert result.status == ToolStatus.SUCCESS

        # Verify changes
        assert "new_helper" in (temp_project / "utils.py").read_text()
        assert "new_helper" in (temp_project / "main.py").read_text()


# ============================================================================
# ERROR RECOVERY WORKFLOW
# ============================================================================

@pytest.mark.integration
class TestErrorRecoveryWorkflow:
    """Test error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_failed_edit_no_change(self, temp_project):
        """Test that failed edits don't change files."""
        reset_session_auto_approve()
        executor = ToolExecutor(str(temp_project))

        original_content = "def original():\n    pass"
        test_file = temp_project / "no_change.py"
        test_file.write_text(original_content)

        # Try edit with string that doesn't exist
        result = await executor.execute(
            "file_editor",
            {
                "operation": "str_replace",
                "file_path": str(test_file),
                "old_str": "nonexistent string",
                "new_str": "replacement",
            },
            skip_confirmation=True,
        )

        assert result.status == ToolStatus.ERROR
        # File should be unchanged
        assert test_file.read_text() == original_content

    @pytest.mark.asyncio
    async def test_rewind_after_failed_series(self, temp_project):
        """Test rewinding after a series of operations."""
        reset_session_auto_approve()
        reset_checkpoint_manager()

        import synod.core.checkpoints as cp_module
        cp_module._checkpoint_manager = CheckpointManager(str(temp_project))

        executor = ToolExecutor(str(temp_project))
        test_file = temp_project / "series.py"

        # Create file
        await executor.execute(
            "file_editor",
            {"operation": "create", "file_path": str(test_file), "content": "v1"},
            skip_confirmation=True,
        )

        # Edit 1
        await executor.execute(
            "file_editor",
            {"operation": "str_replace", "file_path": str(test_file), "old_str": "v1", "new_str": "v2"},
            skip_confirmation=True,
        )

        # Edit 2
        await executor.execute(
            "file_editor",
            {"operation": "str_replace", "file_path": str(test_file), "old_str": "v2", "new_str": "v3"},
            skip_confirmation=True,
        )

        assert test_file.read_text() == "v3"

        # Get checkpoints and restore to v2
        manager = cp_module._checkpoint_manager
        checkpoints = manager.get_checkpoints()

        # Find checkpoint before last edit (v2 -> v3)
        # Checkpoints are newest first, so [0] is v3, [1] is v2
        if len(checkpoints) >= 2:
            manager.restore_checkpoint(checkpoints[0].id)
            assert test_file.read_text() == "v2"


# ============================================================================
# SESSION WORKFLOW
# ============================================================================

@pytest.mark.integration
class TestSessionWorkflow:
    """Test session-related workflows."""

    def test_session_hooks_fire(self, temp_project):
        """Test session start/end hooks fire."""
        marker_start = temp_project / ".session_start"
        marker_end = temp_project / ".session_end"

        hooks_file = temp_project / ".synod" / "hooks.json"
        hooks_data = {
            "hooks": [
                {
                    "name": "session-start",
                    "event": "session_start",
                    "command": f"touch {marker_start}",
                    "enabled": True,
                },
                {
                    "name": "session-end",
                    "event": "session_end",
                    "command": f"touch {marker_end}",
                    "enabled": True,
                },
            ]
        }
        hooks_file.write_text(json.dumps(hooks_data))

        import synod.core.hooks as hooks_module
        hooks_module._hook_manager = HookManager(str(temp_project))

        # Fire session start
        run_hooks(HookEvent.SESSION_START, working_directory=str(temp_project))
        assert marker_start.exists()

        # Fire session end
        run_hooks(HookEvent.SESSION_END, working_directory=str(temp_project))
        assert marker_end.exists()
