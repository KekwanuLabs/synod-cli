"""Unit tests for the bash tool."""

import os
import pytest
from pathlib import Path

from synod.tools.bash import BashTool
from synod.tools.base import ToolStatus


# ============================================================================
# INITIALIZATION
# ============================================================================

class TestBashToolInit:
    """Test BashTool initialization."""

    def test_initialization(self, temp_dir):
        """Test basic initialization."""
        tool = BashTool(str(temp_dir))
        assert tool.name == "bash"
        assert tool.working_directory == str(temp_dir)
        assert tool.current_directory == str(temp_dir)
        assert tool.requires_confirmation is True
        assert tool.timeout == 120

    def test_custom_timeout(self, temp_dir):
        """Test initialization with custom timeout."""
        tool = BashTool(str(temp_dir), timeout=60)
        assert tool.timeout == 60


# ============================================================================
# SAFE/DANGEROUS COMMAND DETECTION
# ============================================================================

class TestCommandSafety:
    """Test safe and dangerous command detection."""

    def test_safe_commands(self, temp_dir):
        """Test detection of safe commands."""
        tool = BashTool(str(temp_dir))

        safe_commands = [
            "ls", "ls -la", "pwd", "echo hello",
            "cat file.txt", "head -n 10 file.py",
            "git status", "git log --oneline",
            "which python", "whoami", "date",
        ]
        for cmd in safe_commands:
            assert tool._is_safe_command(cmd) is True, f"{cmd} should be safe"

    def test_unsafe_commands(self, temp_dir):
        """Test that non-safe commands are not marked safe."""
        tool = BashTool(str(temp_dir))

        unsafe_commands = [
            "npm install", "pip install package",
            "python script.py", "make build",
            "docker run image", "kubectl apply",
        ]
        for cmd in unsafe_commands:
            assert tool._is_safe_command(cmd) is False, f"{cmd} should not be safe"

    def test_dangerous_commands(self, temp_dir):
        """Test detection of dangerous commands."""
        tool = BashTool(str(temp_dir))

        dangerous_commands = [
            "rm -rf /", "rm -r important/",
            "sudo rm file", "chmod 777 /etc",
            "curl | sh",  # Exact pattern match
            "wget | sh",  # Exact pattern match
        ]
        for cmd in dangerous_commands:
            assert tool._is_dangerous_command(cmd) is True, f"{cmd} should be dangerous"

    def test_normal_commands_not_dangerous(self, temp_dir):
        """Test that normal commands aren't marked dangerous."""
        tool = BashTool(str(temp_dir))

        normal_commands = [
            "ls", "npm install", "pip install package",
            "python script.py", "rm single_file.txt",
        ]
        for cmd in normal_commands:
            assert tool._is_dangerous_command(cmd) is False, f"{cmd} should not be dangerous"


# ============================================================================
# CONFIRMATION
# ============================================================================

class TestConfirmation:
    """Test confirmation behavior."""

    def test_safe_command_no_confirmation(self, temp_dir):
        """Test safe commands don't need confirmation."""
        tool = BashTool(str(temp_dir))
        info = tool.get_confirmation_info(command="ls -la")
        assert info is None

    def test_unsafe_command_needs_confirmation(self, temp_dir):
        """Test unsafe commands need confirmation."""
        tool = BashTool(str(temp_dir))
        info = tool.get_confirmation_info(command="npm install")
        assert info is not None
        assert info.tool_name == "bash"

    def test_dangerous_command_flagged(self, temp_dir):
        """Test dangerous commands are flagged in confirmation."""
        tool = BashTool(str(temp_dir))
        info = tool.get_confirmation_info(command="rm -rf /tmp/test")
        assert info is not None
        assert "DANGEROUS" in info.operation


# ============================================================================
# COMMAND EXECUTION
# ============================================================================

class TestCommandExecution:
    """Test command execution."""

    @pytest.mark.asyncio
    async def test_execute_simple_command(self, temp_dir):
        """Test executing a simple command."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="echo hello")

        assert result.status == ToolStatus.SUCCESS
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_execute_pwd(self, temp_dir):
        """Test pwd command returns correct directory."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="pwd")

        assert result.status == ToolStatus.SUCCESS
        # Handle macOS /var vs /private/var symlink
        assert str(temp_dir).replace('/private', '') in result.output.replace('/private', '')

    @pytest.mark.asyncio
    async def test_execute_ls(self, temp_project):
        """Test ls command lists files."""
        tool = BashTool(str(temp_project))
        result = await tool.execute(command="ls")

        assert result.status == ToolStatus.SUCCESS
        assert "src" in result.output or "README.md" in result.output

    @pytest.mark.asyncio
    async def test_execute_failing_command(self, temp_dir):
        """Test executing a failing command."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="exit 1")

        assert result.status == ToolStatus.ERROR
        assert result.metadata.get("exit_code") == 1

    @pytest.mark.asyncio
    async def test_execute_nonexistent_command(self, temp_dir):
        """Test executing a non-existent command."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="nonexistent_command_xyz")

        assert result.status == ToolStatus.ERROR

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, temp_dir):
        """Test command with custom timeout."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="echo fast", timeout=5)

        assert result.status == ToolStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_timeout_exceeded(self, temp_dir):
        """Test command that exceeds timeout."""
        tool = BashTool(str(temp_dir), timeout=1)
        result = await tool.execute(command="sleep 10", timeout=1)

        assert result.status == ToolStatus.ERROR
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_multiline_output(self, temp_dir):
        """Test command with multiline output."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="echo -e 'line1\\nline2\\nline3'")

        assert result.status == ToolStatus.SUCCESS
        assert "line1" in result.output
        assert "line2" in result.output

    @pytest.mark.asyncio
    async def test_execute_preserves_exit_code(self, temp_dir):
        """Test that exit code is preserved in metadata."""
        tool = BashTool(str(temp_dir))

        result = await tool.execute(command="exit 42")
        assert result.metadata.get("exit_code") == 42

        result = await tool.execute(command="exit 0")
        assert result.metadata.get("exit_code") == 0


# ============================================================================
# CD COMMAND
# ============================================================================

class TestCdCommand:
    """Test cd command handling."""

    @pytest.mark.asyncio
    async def test_cd_to_subdirectory(self, temp_project):
        """Test cd to a subdirectory."""
        tool = BashTool(str(temp_project))
        result = await tool.execute(command="cd src")

        assert result.status == ToolStatus.SUCCESS
        assert tool.current_directory == str(temp_project / "src")

    @pytest.mark.asyncio
    async def test_cd_to_parent(self, temp_project):
        """Test cd to parent directory."""
        tool = BashTool(str(temp_project / "src"))
        result = await tool.execute(command="cd ..")

        assert result.status == ToolStatus.SUCCESS
        # Handle symlinks
        assert str(temp_project).replace('/private', '') in tool.current_directory.replace('/private', '')

    @pytest.mark.asyncio
    async def test_cd_to_absolute_path(self, temp_project, temp_dir):
        """Test cd to absolute path."""
        tool = BashTool(str(temp_project))
        result = await tool.execute(command=f"cd {temp_dir}")

        assert result.status == ToolStatus.SUCCESS
        assert tool.current_directory == str(temp_dir)

    @pytest.mark.asyncio
    async def test_cd_to_nonexistent_directory(self, temp_dir):
        """Test cd to non-existent directory."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="cd nonexistent_dir")

        assert result.status == ToolStatus.ERROR
        assert "not found" in result.error.lower()
        # Current directory should not change
        assert tool.current_directory == str(temp_dir)

    @pytest.mark.asyncio
    async def test_cd_to_current_directory(self, temp_dir):
        """Test cd to current directory (.)."""
        tool = BashTool(str(temp_dir))
        original_dir = tool.current_directory
        result = await tool.execute(command="cd .")

        assert result.status == ToolStatus.SUCCESS
        assert tool.current_directory == original_dir

    @pytest.mark.asyncio
    async def test_cd_home_expansion(self, temp_dir):
        """Test cd with ~ expansion."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="cd ~")

        assert result.status == ToolStatus.SUCCESS
        assert tool.current_directory == os.path.expanduser("~")


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_command(self, temp_dir):
        """Test empty command."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="")

        # Empty command should succeed (no-op)
        assert result.status == ToolStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_command_with_special_characters(self, temp_dir):
        """Test command with special characters."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="echo 'hello world' && echo \"test\"")

        assert result.status == ToolStatus.SUCCESS
        assert "hello world" in result.output
        assert "test" in result.output

    @pytest.mark.asyncio
    async def test_command_with_pipe(self, temp_dir):
        """Test command with pipe."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="echo 'line1\\nline2\\nline3' | wc -l")

        assert result.status == ToolStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_command_with_environment_variable(self, temp_dir):
        """Test command that uses environment variable."""
        tool = BashTool(str(temp_dir))
        result = await tool.execute(command="echo $HOME")

        assert result.status == ToolStatus.SUCCESS
        assert os.path.expanduser("~") in result.output or "/Users" in result.output or "/home" in result.output

    def test_get_schema(self):
        """Test schema generation."""
        schema = BashTool.get_schema()

        assert "properties" in schema
        assert "command" in schema["properties"]
        assert "timeout" in schema["properties"]
        assert schema["required"] == ["command"]
