"""Unit tests for the context module."""

import pytest
from pathlib import Path

from synod.core.context import read_file_content


# ============================================================================
# READ FILE CONTENT
# ============================================================================

class TestReadFileContent:
    """Test read_file_content function."""

    def test_empty_file_paths(self):
        """Test with empty file paths list."""
        result = read_file_content([])
        assert result == ""

    def test_read_single_file(self, temp_dir):
        """Test reading a single file."""
        # Create test file
        test_file = temp_dir / "test.py"
        test_file.write_text("def hello():\n    pass")

        result = read_file_content(["test.py"], base_dir=str(temp_dir))

        assert "--- START FILE: test.py ---" in result
        assert "def hello():" in result
        assert "--- END FILE: test.py ---" in result

    def test_read_multiple_files(self, temp_dir):
        """Test reading multiple files."""
        # Create test files
        (temp_dir / "file1.py").write_text("# File 1")
        (temp_dir / "file2.py").write_text("# File 2")

        result = read_file_content(["file1.py", "file2.py"], base_dir=str(temp_dir))

        assert "--- START FILE: file1.py ---" in result
        assert "--- START FILE: file2.py ---" in result
        assert "# File 1" in result
        assert "# File 2" in result

    def test_nonexistent_file(self, temp_dir):
        """Test with non-existent file."""
        result = read_file_content(["nonexistent.py"], base_dir=str(temp_dir))

        assert "--- File Not Found: nonexistent.py ---" in result

    def test_directory_path(self, temp_dir):
        """Test with directory path instead of file."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        result = read_file_content(["subdir"], base_dir=str(temp_dir))

        assert "--- Path is a Directory: subdir ---" in result

    def test_absolute_path(self, temp_dir):
        """Test with absolute file path."""
        test_file = temp_dir / "absolute_test.py"
        test_file.write_text("# Absolute path test")

        result = read_file_content([str(test_file)])

        assert "# Absolute path test" in result

    def test_mixed_valid_invalid_files(self, temp_dir):
        """Test with mix of valid and invalid files."""
        (temp_dir / "valid.py").write_text("# Valid file")

        result = read_file_content(
            ["valid.py", "invalid.py"],
            base_dir=str(temp_dir)
        )

        assert "# Valid file" in result
        assert "--- File Not Found: invalid.py ---" in result

    def test_file_with_unicode(self, temp_dir):
        """Test reading file with unicode content."""
        test_file = temp_dir / "unicode.py"
        test_file.write_text("# Unicode: \u2603 \u2764 \u2714", encoding="utf-8")

        result = read_file_content(["unicode.py"], base_dir=str(temp_dir))

        assert "\u2603" in result
        assert "\u2764" in result

    def test_default_base_dir(self, temp_dir, monkeypatch):
        """Test using default current directory."""
        monkeypatch.chdir(temp_dir)
        (temp_dir / "cwd_test.py").write_text("# CWD test")

        result = read_file_content(["cwd_test.py"])

        assert "# CWD test" in result

    def test_multiline_content(self, temp_dir):
        """Test reading file with multiline content."""
        content = """def foo():
    print("hello")
    return 42

def bar():
    pass
"""
        (temp_dir / "multiline.py").write_text(content)

        result = read_file_content(["multiline.py"], base_dir=str(temp_dir))

        assert "def foo():" in result
        assert 'print("hello")' in result
        assert "def bar():" in result

    def test_empty_file(self, temp_dir):
        """Test reading empty file."""
        (temp_dir / "empty.py").write_text("")

        result = read_file_content(["empty.py"], base_dir=str(temp_dir))

        assert "--- START FILE: empty.py ---" in result
        assert "--- END FILE: empty.py ---" in result
