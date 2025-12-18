"""Unit tests for the file editor tool."""

import os
import pytest
from pathlib import Path

from synod.tools.file_editor import FileEditorTool
from synod.tools.base import ToolStatus


# ============================================================================
# INITIALIZATION
# ============================================================================

class TestFileEditorInit:
    """Test FileEditorTool initialization."""

    def test_initialization(self, temp_dir):
        """Test basic initialization."""
        tool = FileEditorTool(str(temp_dir))
        assert tool.name == "file_editor"
        assert tool.working_directory == str(temp_dir)
        assert tool.requires_confirmation is True

    def test_resolve_relative_path(self, temp_dir):
        """Test resolving relative paths."""
        tool = FileEditorTool(str(temp_dir))
        resolved = tool._resolve_path("src/main.py")
        assert resolved == os.path.join(str(temp_dir), "src/main.py")

    def test_resolve_absolute_path(self, temp_dir):
        """Test resolving absolute paths."""
        tool = FileEditorTool(str(temp_dir))
        resolved = tool._resolve_path("/absolute/path/file.py")
        assert resolved == "/absolute/path/file.py"


# ============================================================================
# VIEW OPERATION
# ============================================================================

class TestViewOperation:
    """Test file viewing operations."""

    @pytest.mark.asyncio
    async def test_view_file(self, temp_dir, sample_python_file):
        """Test viewing a file."""
        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="view",
            file_path=str(sample_python_file),
        )

        assert result.status == ToolStatus.SUCCESS
        assert "def hello" in result.output
        assert "def add" in result.output

    @pytest.mark.asyncio
    async def test_view_file_with_line_numbers(self, temp_dir, sample_python_file):
        """Test view output includes line numbers."""
        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="view",
            file_path=str(sample_python_file),
        )

        # Should have line numbers
        assert "1\t" in result.output or "     1\t" in result.output

    @pytest.mark.asyncio
    async def test_view_file_range(self, temp_dir, sample_python_file):
        """Test viewing specific line range."""
        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="view",
            file_path=str(sample_python_file),
            start_line=1,
            end_line=5,
        )

        assert result.status == ToolStatus.SUCCESS
        assert "metadata" in result.__dict__
        assert result.metadata.get("shown_lines") <= 5

    @pytest.mark.asyncio
    async def test_view_nonexistent_file(self, temp_dir):
        """Test viewing a file that doesn't exist."""
        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="view",
            file_path=str(temp_dir / "nonexistent.py"),
        )

        assert result.status == ToolStatus.ERROR
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_view_directory(self, temp_project):
        """Test viewing a directory."""
        tool = FileEditorTool(str(temp_project))
        result = await tool.execute(
            operation="view",
            file_path=str(temp_project / "src"),
        )

        assert result.status == ToolStatus.SUCCESS
        assert "main.py" in result.output
        assert result.metadata.get("type") == "directory"


# ============================================================================
# CREATE OPERATION
# ============================================================================

class TestCreateOperation:
    """Test file creation operations."""

    @pytest.mark.asyncio
    async def test_create_file(self, temp_dir):
        """Test creating a new file."""
        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="create",
            file_path=str(temp_dir / "new_file.py"),
            content="print('hello world')",
        )

        assert result.status == ToolStatus.SUCCESS
        assert (temp_dir / "new_file.py").exists()
        assert (temp_dir / "new_file.py").read_text() == "print('hello world')"

    @pytest.mark.asyncio
    async def test_create_file_with_directories(self, temp_dir):
        """Test creating file in non-existent directory."""
        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="create",
            file_path=str(temp_dir / "deep" / "nested" / "file.py"),
            content="# nested file",
        )

        assert result.status == ToolStatus.SUCCESS
        assert (temp_dir / "deep" / "nested" / "file.py").exists()

    @pytest.mark.asyncio
    async def test_create_existing_file_fails(self, temp_dir, sample_python_file):
        """Test creating file that already exists fails."""
        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="create",
            file_path=str(sample_python_file),
            content="new content",
        )

        assert result.status == ToolStatus.ERROR
        assert "already exists" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_records_history(self, temp_dir):
        """Test that create records in edit history."""
        tool = FileEditorTool(str(temp_dir))
        await tool.execute(
            operation="create",
            file_path=str(temp_dir / "tracked.py"),
            content="# tracked",
        )

        assert len(tool.edit_history) == 1
        assert tool.edit_history[0]["operation"] == "create"


# ============================================================================
# STR_REPLACE OPERATION
# ============================================================================

class TestStrReplaceOperation:
    """Test string replacement operations."""

    @pytest.mark.asyncio
    async def test_str_replace_simple(self, temp_dir):
        """Test simple string replacement."""
        # Create a file
        test_file = temp_dir / "replace_test.py"
        test_file.write_text("def old_name():\n    pass")

        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="str_replace",
            file_path=str(test_file),
            old_str="old_name",
            new_str="new_name",
        )

        assert result.status == ToolStatus.SUCCESS
        assert test_file.read_text() == "def new_name():\n    pass"

    @pytest.mark.asyncio
    async def test_str_replace_multiline(self, temp_dir):
        """Test multiline string replacement."""
        test_file = temp_dir / "multiline.py"
        test_file.write_text("def func():\n    old_code\n    more_old")

        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="str_replace",
            file_path=str(test_file),
            old_str="def func():\n    old_code\n    more_old",
            new_str="def func():\n    new_code\n    better_code",
        )

        assert result.status == ToolStatus.SUCCESS
        assert "new_code" in test_file.read_text()

    @pytest.mark.asyncio
    async def test_str_replace_not_found(self, temp_dir):
        """Test replacement when string not found."""
        test_file = temp_dir / "no_match.py"
        test_file.write_text("def hello():\n    pass")

        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="str_replace",
            file_path=str(test_file),
            old_str="nonexistent_string",
            new_str="replacement",
        )

        assert result.status == ToolStatus.ERROR
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_str_replace_multiple_occurrences(self, temp_dir):
        """Test replacement with multiple occurrences fails."""
        test_file = temp_dir / "multiple.py"
        test_file.write_text("pass\npass\npass")

        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="str_replace",
            file_path=str(test_file),
            old_str="pass",
            new_str="return",
        )

        assert result.status == ToolStatus.ERROR
        assert "3 times" in result.error or "multiple" in result.error.lower()

    @pytest.mark.asyncio
    async def test_str_replace_nonexistent_file(self, temp_dir):
        """Test replacement on non-existent file."""
        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="str_replace",
            file_path=str(temp_dir / "nonexistent.py"),
            old_str="old",
            new_str="new",
        )

        assert result.status == ToolStatus.ERROR
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_str_replace_generates_diff(self, temp_dir):
        """Test that str_replace generates a diff."""
        test_file = temp_dir / "diff_test.py"
        test_file.write_text("value = 1")

        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="str_replace",
            file_path=str(test_file),
            old_str="value = 1",
            new_str="value = 2",
        )

        assert result.status == ToolStatus.SUCCESS
        assert "diff" in result.metadata or "-value = 1" in result.output

    @pytest.mark.asyncio
    async def test_str_replace_records_history(self, temp_dir):
        """Test that str_replace records in edit history."""
        test_file = temp_dir / "history_test.py"
        test_file.write_text("original")

        tool = FileEditorTool(str(temp_dir))
        await tool.execute(
            operation="str_replace",
            file_path=str(test_file),
            old_str="original",
            new_str="modified",
        )

        assert len(tool.edit_history) == 1
        assert tool.edit_history[0]["operation"] == "str_replace"
        assert tool.edit_history[0]["old_content"] == "original"


# ============================================================================
# CONFIRMATION
# ============================================================================

class TestConfirmation:
    """Test confirmation behavior."""

    def test_view_no_confirmation(self, temp_dir, sample_python_file):
        """Test view operation doesn't need confirmation."""
        tool = FileEditorTool(str(temp_dir))
        info = tool.get_confirmation_info(
            operation="view",
            file_path=str(sample_python_file),
        )
        assert info is None

    def test_create_needs_confirmation(self, temp_dir):
        """Test create operation needs confirmation."""
        tool = FileEditorTool(str(temp_dir))
        info = tool.get_confirmation_info(
            operation="create",
            file_path=str(temp_dir / "new.py"),
            content="# content",
        )
        assert info is not None
        assert info.operation == "Create file"

    def test_str_replace_needs_confirmation(self, temp_dir, sample_python_file):
        """Test str_replace operation needs confirmation."""
        tool = FileEditorTool(str(temp_dir))
        info = tool.get_confirmation_info(
            operation="str_replace",
            file_path=str(sample_python_file),
            old_str="hello",
            new_str="goodbye",
        )
        assert info is not None
        assert info.operation == "Edit file"


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_unknown_operation(self, temp_dir):
        """Test unknown operation returns error."""
        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="invalid_op",
            file_path=str(temp_dir / "file.py"),
        )

        assert result.status == ToolStatus.ERROR
        assert "unknown operation" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_content_create(self, temp_dir):
        """Test creating file with empty content."""
        tool = FileEditorTool(str(temp_dir))
        result = await tool.execute(
            operation="create",
            file_path=str(temp_dir / "empty.py"),
            content="",
        )

        assert result.status == ToolStatus.SUCCESS
        assert (temp_dir / "empty.py").read_text() == ""

    def test_is_text_file(self, temp_dir):
        """Test text file detection."""
        tool = FileEditorTool(str(temp_dir))

        assert tool._is_text_file("main.py") is True
        assert tool._is_text_file("config.json") is True
        assert tool._is_text_file("Makefile") is True
        assert tool._is_text_file("Dockerfile") is True
        assert tool._is_text_file("image.png") is False
