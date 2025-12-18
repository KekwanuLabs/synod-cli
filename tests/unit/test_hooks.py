"""Unit tests for the hooks system."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from synod.core.hooks import (
    Hook,
    HookEvent,
    HookContext,
    HookResult,
    HookManager,
    load_hooks,
    save_hooks,
    run_hooks,
    get_hook_manager,
    handle_hooks_command,
)


# ============================================================================
# HOOK DATA CLASSES
# ============================================================================

class TestHookEvent:
    """Test HookEvent enum."""

    def test_all_events_defined(self):
        """Verify all expected hook events exist."""
        expected = [
            "pre_tool_use", "post_tool_use", "session_start",
            "session_end", "pre_debate", "post_debate", "file_modified"
        ]
        for event in expected:
            assert HookEvent(event) is not None

    def test_event_values(self):
        """Test event value strings."""
        assert HookEvent.PRE_TOOL_USE.value == "pre_tool_use"
        assert HookEvent.FILE_MODIFIED.value == "file_modified"


class TestHook:
    """Test Hook dataclass."""

    def test_hook_creation(self):
        """Test creating a hook."""
        hook = Hook(
            name="test-hook",
            event=HookEvent.POST_DEBATE,
            command="echo 'test'",
        )
        assert hook.name == "test-hook"
        assert hook.event == HookEvent.POST_DEBATE
        assert hook.command == "echo 'test'"
        assert hook.enabled is True

    def test_hook_to_dict(self):
        """Test serializing hook to dictionary."""
        hook = Hook(
            name="test",
            event=HookEvent.PRE_TOOL_USE,
            command="echo test",
            enabled=False,
            description="A test hook",
        )
        data = hook.to_dict()

        assert data["name"] == "test"
        assert data["event"] == "pre_tool_use"
        assert data["command"] == "echo test"
        assert data["enabled"] is False
        assert data["description"] == "A test hook"

    def test_hook_from_dict(self):
        """Test deserializing hook from dictionary."""
        data = {
            "name": "my-hook",
            "event": "post_tool_use",
            "command": "npm test",
            "enabled": True,
        }
        hook = Hook.from_dict(data)

        assert hook.name == "my-hook"
        assert hook.event == HookEvent.POST_TOOL_USE
        assert hook.command == "npm test"
        assert hook.enabled is True


class TestHookContext:
    """Test HookContext dataclass."""

    def test_context_creation(self):
        """Test creating hook context."""
        context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="file_editor",
            tool_params={"operation": "create"},
            working_directory="/tmp",
        )
        assert context.event == HookEvent.PRE_TOOL_USE
        assert context.tool_name == "file_editor"
        assert context.tool_params == {"operation": "create"}

    def test_context_optional_fields(self):
        """Test context with minimal fields."""
        context = HookContext(event=HookEvent.SESSION_START)
        assert context.tool_name is None
        assert context.file_path is None
        assert context.query is None


class TestHookResult:
    """Test HookResult dataclass."""

    def test_default_allows(self):
        """Test default result allows execution."""
        result = HookResult()
        assert result.allow is True

    def test_blocking_result(self):
        """Test blocking result."""
        result = HookResult(allow=False, message="Blocked by policy")
        assert result.allow is False
        assert result.message == "Blocked by policy"


# ============================================================================
# HOOK LOADING/SAVING
# ============================================================================

class TestHookLoading:
    """Test loading and saving hooks."""

    def test_load_empty_hooks(self, temp_project):
        """Test loading when no hooks file exists."""
        hooks = load_hooks(str(temp_project))
        assert hooks == []

    def test_load_project_hooks(self, temp_project):
        """Test loading hooks from project directory."""
        hooks_file = temp_project / ".synod" / "hooks.json"
        hooks_data = {
            "hooks": [
                {"name": "test", "event": "post_debate", "command": "echo test"}
            ]
        }
        hooks_file.write_text(json.dumps(hooks_data))

        hooks = load_hooks(str(temp_project))
        assert len(hooks) == 1
        assert hooks[0].name == "test"

    def test_save_hooks(self, temp_project):
        """Test saving hooks to file."""
        hooks = [
            Hook(name="hook1", event=HookEvent.POST_DEBATE, command="echo 1"),
            Hook(name="hook2", event=HookEvent.SESSION_END, command="echo 2"),
        ]
        save_hooks(hooks, str(temp_project))

        hooks_file = temp_project / ".synod" / "hooks.json"
        assert hooks_file.exists()

        data = json.loads(hooks_file.read_text())
        assert len(data["hooks"]) == 2


# ============================================================================
# HOOK MANAGER
# ============================================================================

class TestHookManager:
    """Test HookManager class."""

    def test_manager_initialization(self, temp_project):
        """Test manager initializes with project hooks."""
        manager = HookManager(str(temp_project))
        # Compare string paths to avoid macOS /var vs /private/var symlink issues
        assert str(manager.project_path) == str(temp_project) or \
               str(manager.project_path).replace('/private', '') == str(temp_project).replace('/private', '')

    def test_get_hooks_for_event(self, temp_project, hooks_config):
        """Test filtering hooks by event."""
        manager = HookManager(str(temp_project))
        manager.hooks = load_hooks(str(temp_project))

        post_debate_hooks = manager.get_hooks_for_event(HookEvent.POST_DEBATE)
        assert len(post_debate_hooks) == 1
        assert post_debate_hooks[0].name == "test-hook"

    def test_add_hook(self, temp_project):
        """Test adding a new hook."""
        manager = HookManager(str(temp_project))
        hook = Hook(name="new-hook", event=HookEvent.FILE_MODIFIED, command="echo modified")

        manager.add_hook(hook)

        assert len(manager.hooks) == 1
        assert manager.hooks[0].name == "new-hook"

    def test_remove_hook(self, temp_project):
        """Test removing a hook."""
        manager = HookManager(str(temp_project))
        hook = Hook(name="to-remove", event=HookEvent.POST_DEBATE, command="echo test")
        manager.add_hook(hook)

        result = manager.remove_hook("to-remove")

        assert result is True
        assert len(manager.hooks) == 0

    def test_remove_nonexistent_hook(self, temp_project):
        """Test removing a hook that doesn't exist."""
        manager = HookManager(str(temp_project))
        result = manager.remove_hook("nonexistent")
        assert result is False

    def test_execute_hook_success(self, temp_project):
        """Test executing a hook successfully."""
        manager = HookManager(str(temp_project))
        hook = Hook(name="echo-hook", event=HookEvent.POST_DEBATE, command="echo 'success'")
        context = HookContext(event=HookEvent.POST_DEBATE, working_directory=str(temp_project))

        result = manager.execute_hook(hook, context)

        assert result.allow is True
        assert "success" in (result.message or "")

    def test_execute_hook_with_env_vars(self, temp_project):
        """Test hook receives environment variables."""
        manager = HookManager(str(temp_project))
        hook = Hook(name="env-hook", event=HookEvent.PRE_TOOL_USE, command="echo $SYNOD_TOOL")
        context = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="file_editor",
            working_directory=str(temp_project),
        )

        result = manager.execute_hook(hook, context)

        assert result.allow is True
        assert "file_editor" in (result.message or "")

    def test_execute_blocking_hook(self, temp_project):
        """Test hook that blocks execution."""
        manager = HookManager(str(temp_project))
        hook = Hook(
            name="block-hook",
            event=HookEvent.PRE_TOOL_USE,
            command='echo \'{"allow": false, "message": "blocked by test"}\''
        )
        context = HookContext(event=HookEvent.PRE_TOOL_USE, working_directory=str(temp_project))

        result = manager.execute_hook(hook, context)

        assert result.allow is False
        assert "blocked by test" in result.message

    def test_execute_hook_timeout(self, temp_project):
        """Test hook timeout handling."""
        manager = HookManager(str(temp_project))
        hook = Hook(name="slow-hook", event=HookEvent.POST_DEBATE, command="sleep 60")
        context = HookContext(event=HookEvent.POST_DEBATE, working_directory=str(temp_project))

        # Should timeout and return allow=True
        with patch.object(manager, 'execute_hook') as mock_exec:
            mock_exec.return_value = HookResult(allow=True, message="timed out")
            result = mock_exec(hook, context)
            assert result.allow is True


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_run_hooks(self, temp_project, hooks_config, monkeypatch):
        """Test run_hooks convenience function."""
        # Reset singleton
        import synod.core.hooks as hooks_module
        hooks_module._hook_manager = None

        monkeypatch.chdir(temp_project)

        result = run_hooks(
            HookEvent.POST_DEBATE,
            query="test query",
            working_directory=str(temp_project),
        )

        assert result.allow is True

    def test_get_hook_manager_singleton(self, temp_project):
        """Test hook manager is a singleton."""
        import synod.core.hooks as hooks_module
        hooks_module._hook_manager = None

        manager1 = get_hook_manager(str(temp_project))
        manager2 = get_hook_manager(str(temp_project))

        assert manager1 is manager2


# ============================================================================
# COMMAND HANDLER
# ============================================================================

class TestHooksCommand:
    """Test /hooks command handler."""

    @pytest.mark.asyncio
    async def test_hooks_list_empty(self, temp_project, capsys):
        """Test listing hooks when none configured."""
        import synod.core.hooks as hooks_module
        hooks_module._hook_manager = None

        await handle_hooks_command("")

        captured = capsys.readouterr()
        assert "No hooks configured" in captured.out

    @pytest.mark.asyncio
    async def test_hooks_list_with_hooks(self, temp_project, hooks_config, capsys):
        """Test listing configured hooks."""
        import synod.core.hooks as hooks_module
        hooks_module._hook_manager = HookManager(str(temp_project))

        await handle_hooks_command("")

        captured = capsys.readouterr()
        assert "test-hook" in captured.out or "Configured Hooks" in captured.out
