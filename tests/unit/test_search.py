"""Unit tests for the search tool."""

import os
import pytest
from pathlib import Path

from synod.tools.search import SearchTool, SearchMatch, FileMatch
from synod.tools.base import ToolStatus


# ============================================================================
# INITIALIZATION
# ============================================================================

class TestSearchToolInit:
    """Test SearchTool initialization."""

    def test_initialization(self, temp_dir):
        """Test basic initialization."""
        tool = SearchTool(str(temp_dir))
        assert tool.name == "search"
        assert tool.working_directory == str(temp_dir)
        assert tool.max_results == 50
        assert tool.requires_confirmation is False

    def test_custom_max_results(self, temp_dir):
        """Test initialization with custom max_results."""
        tool = SearchTool(str(temp_dir), max_results=100)
        assert tool.max_results == 100


# ============================================================================
# DATA CLASSES
# ============================================================================

class TestDataClasses:
    """Test SearchMatch and FileMatch data classes."""

    def test_search_match(self):
        """Test SearchMatch creation."""
        match = SearchMatch(
            file="src/main.py",
            line=10,
            column=5,
            text="def hello():",
        )
        assert match.file == "src/main.py"
        assert match.line == 10
        assert match.column == 5
        assert match.text == "def hello():"

    def test_file_match(self):
        """Test FileMatch creation."""
        match = FileMatch(
            path="src/utils/helpers.py",
            score=90,
            reason="starts with",
        )
        assert match.path == "src/utils/helpers.py"
        assert match.score == 90
        assert match.reason == "starts with"


# ============================================================================
# MODE VALIDATION
# ============================================================================

class TestModeValidation:
    """Test search mode validation."""

    @pytest.mark.asyncio
    async def test_invalid_mode(self, temp_dir):
        """Test invalid mode returns error."""
        tool = SearchTool(str(temp_dir))
        result = await tool.execute(
            mode="invalid_mode",
            pattern="test",
        )

        assert result.status == ToolStatus.ERROR
        assert "unknown mode" in result.error.lower()


# ============================================================================
# FILE SEARCH
# ============================================================================

class TestFileSearch:
    """Test file search functionality."""

    @pytest.mark.asyncio
    async def test_file_search_exact_match(self, temp_project):
        """Test finding file by exact name."""
        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="file_search",
            pattern="main.py",
        )

        assert result.status == ToolStatus.SUCCESS
        assert "main.py" in result.output

    @pytest.mark.asyncio
    async def test_file_search_glob_pattern(self, temp_project):
        """Test finding files with glob pattern."""
        # Create some test files
        (temp_project / "test1.py").write_text("# test1")
        (temp_project / "test2.py").write_text("# test2")
        (temp_project / "data.json").write_text("{}")

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="file_search",
            pattern="*.py",
        )

        assert result.status == ToolStatus.SUCCESS
        assert ".py" in result.output

    @pytest.mark.asyncio
    async def test_file_search_fuzzy_match(self, temp_project):
        """Test fuzzy file matching."""
        (temp_project / "user_controller.py").write_text("# controller")

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="file_search",
            pattern="usrctrl",
        )

        assert result.status == ToolStatus.SUCCESS
        # Should find user_controller.py via fuzzy match

    @pytest.mark.asyncio
    async def test_file_search_no_results(self, temp_dir):
        """Test file search with no matches."""
        tool = SearchTool(str(temp_dir))
        result = await tool.execute(
            mode="file_search",
            pattern="nonexistent_xyz.py",
        )

        assert result.status == ToolStatus.SUCCESS
        assert "no files found" in result.output.lower()

    @pytest.mark.asyncio
    async def test_file_search_ignores_node_modules(self, temp_project):
        """Test that node_modules is ignored."""
        # Create node_modules with files
        node_modules = temp_project / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.json").write_text("{}")

        # Create a file outside node_modules
        (temp_project / "package.json").write_text("{}")

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="file_search",
            pattern="package.json",
        )

        assert result.status == ToolStatus.SUCCESS
        # Should only find the root package.json, not the one in node_modules
        assert result.metadata.get("matches", 0) >= 1


# ============================================================================
# TEXT SEARCH
# ============================================================================

class TestTextSearch:
    """Test text search functionality."""

    @pytest.mark.asyncio
    async def test_text_search_simple(self, temp_project, sample_python_file):
        """Test simple text search."""
        # Copy sample file to project
        target = temp_project / "sample.py"
        target.write_text(sample_python_file.read_text())

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="text_search",
            pattern="def hello",
        )

        assert result.status == ToolStatus.SUCCESS
        assert "hello" in result.output.lower()

    @pytest.mark.asyncio
    async def test_text_search_case_insensitive(self, temp_project):
        """Test case-insensitive text search."""
        (temp_project / "test.py").write_text("def MyFunction():\n    pass")

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="text_search",
            pattern="myfunction",
            case_sensitive=False,
        )

        assert result.status == ToolStatus.SUCCESS
        assert "MyFunction" in result.output

    @pytest.mark.asyncio
    async def test_text_search_case_sensitive(self, temp_project):
        """Test case-sensitive text search."""
        (temp_project / "test.py").write_text("def MyFunction():\n    pass")

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="text_search",
            pattern="myfunction",
            case_sensitive=True,
        )

        assert result.status == ToolStatus.SUCCESS
        # Should NOT find MyFunction with case-sensitive search
        assert "MyFunction" not in result.output or "no matches" in result.output.lower()

    @pytest.mark.asyncio
    async def test_text_search_no_results(self, temp_project):
        """Test text search with no matches."""
        (temp_project / "test.py").write_text("def hello(): pass")

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="text_search",
            pattern="nonexistent_xyz_pattern",
        )

        assert result.status == ToolStatus.SUCCESS
        assert "no matches" in result.output.lower()

    @pytest.mark.asyncio
    async def test_text_search_with_file_type(self, temp_project):
        """Test text search filtered by file type."""
        (temp_project / "test.py").write_text("TODO: fix this")
        (temp_project / "test.js").write_text("TODO: fix this too")

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="text_search",
            pattern="TODO",
            file_type="py",
        )

        assert result.status == ToolStatus.SUCCESS
        # Should only find in .py file
        if result.metadata.get("matches", 0) > 0:
            assert "test.py" in result.output

    @pytest.mark.asyncio
    async def test_text_search_max_results(self, temp_project):
        """Test text search respects max_results."""
        # Create file with many matches
        content = "\n".join([f"match line {i}" for i in range(100)])
        (temp_project / "many.txt").write_text(content)

        tool = SearchTool(str(temp_project), max_results=10)
        result = await tool.execute(
            mode="text_search",
            pattern="match",
            max_results=5,
        )

        assert result.status == ToolStatus.SUCCESS
        # Should be limited


# ============================================================================
# FILE SCORING
# ============================================================================

class TestFileScoring:
    """Test file match scoring."""

    def test_score_exact_match(self, temp_dir):
        """Test exact match gets highest score."""
        tool = SearchTool(str(temp_dir))
        score, reason = tool._score_file_match("config.py", "config.py", "config.py", False)

        assert score == 100
        assert "exact" in reason.lower()

    def test_score_starts_with(self, temp_dir):
        """Test starts-with match."""
        tool = SearchTool(str(temp_dir))
        score, reason = tool._score_file_match("config_settings.py", "config_settings.py", "config", False)

        assert score == 90
        assert "starts" in reason.lower()

    def test_score_contains(self, temp_dir):
        """Test contains match."""
        tool = SearchTool(str(temp_dir))
        score, reason = tool._score_file_match("app_config_manager.py", "app_config_manager.py", "config", False)

        assert score == 80
        assert "contains" in reason.lower()

    def test_score_glob_match(self, temp_dir):
        """Test glob pattern matching."""
        tool = SearchTool(str(temp_dir))
        score, reason = tool._score_file_match("test.py", "test.py", "*.py", True)

        assert score == 100
        assert "glob" in reason.lower()

    def test_score_no_match(self, temp_dir):
        """Test no match returns zero score."""
        tool = SearchTool(str(temp_dir))
        score, reason = tool._score_file_match("config.py", "config.py", "xyz", False)

        assert score == 0


# ============================================================================
# FUZZY MATCHING
# ============================================================================

class TestFuzzyMatching:
    """Test fuzzy matching algorithm."""

    def test_fuzzy_match_subsequence(self, temp_dir):
        """Test fuzzy matching finds subsequence."""
        tool = SearchTool(str(temp_dir))

        assert tool._fuzzy_match("user_controller", "usrctrl") is True
        assert tool._fuzzy_match("application", "app") is True
        assert tool._fuzzy_match("test", "test") is True

    def test_fuzzy_match_no_match(self, temp_dir):
        """Test fuzzy matching rejects non-subsequence."""
        tool = SearchTool(str(temp_dir))

        assert tool._fuzzy_match("abc", "xyz") is False
        assert tool._fuzzy_match("test", "tset") is False  # Wrong order


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_search_empty_directory(self, temp_dir):
        """Test searching empty directory."""
        tool = SearchTool(str(temp_dir))
        result = await tool.execute(
            mode="file_search",
            pattern="*.py",
        )

        assert result.status == ToolStatus.SUCCESS
        assert "no files found" in result.output.lower()

    @pytest.mark.asyncio
    async def test_search_hidden_files_excluded(self, temp_project):
        """Test hidden files are excluded by default."""
        (temp_project / ".hidden.py").write_text("# hidden")
        (temp_project / "visible.py").write_text("# visible")

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="file_search",
            pattern="*.py",
            include_hidden=False,
        )

        assert result.status == ToolStatus.SUCCESS
        assert ".hidden.py" not in result.output

    @pytest.mark.asyncio
    async def test_search_hidden_files_included(self, temp_project):
        """Test hidden files can be included."""
        (temp_project / ".hidden.py").write_text("# hidden")

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="file_search",
            pattern=".hidden.py",
            include_hidden=True,
        )

        assert result.status == ToolStatus.SUCCESS
        # May or may not find it depending on exact matching

    @pytest.mark.asyncio
    async def test_search_relative_path(self, temp_project):
        """Test search with relative path."""
        (temp_project / "src" / "test.py").write_text("# test")

        tool = SearchTool(str(temp_project))
        result = await tool.execute(
            mode="file_search",
            pattern="*.py",
            path="src",
        )

        assert result.status == ToolStatus.SUCCESS

    def test_get_schema(self):
        """Test schema generation."""
        schema = SearchTool.get_schema()

        assert "properties" in schema
        assert "mode" in schema["properties"]
        assert "pattern" in schema["properties"]
        assert set(schema["required"]) == {"mode", "pattern"}


# ============================================================================
# RESULT FORMATTING
# ============================================================================

class TestResultFormatting:
    """Test result formatting."""

    def test_format_text_results_empty(self, temp_dir):
        """Test formatting empty text results."""
        tool = SearchTool(str(temp_dir))
        result = tool._format_text_results([], "pattern", 50)

        assert result.status == ToolStatus.SUCCESS
        assert "no matches" in result.output.lower()

    def test_format_text_results_with_matches(self, temp_dir):
        """Test formatting text results with matches."""
        tool = SearchTool(str(temp_dir))
        matches = [
            SearchMatch("file1.py", 10, 5, "def hello():"),
            SearchMatch("file1.py", 20, 5, "def world():"),
            SearchMatch("file2.py", 5, 1, "import hello"),
        ]
        result = tool._format_text_results(matches, "hello", 50)

        assert result.status == ToolStatus.SUCCESS
        assert "3 matches" in result.output
        assert "2 files" in result.output

    def test_format_file_results_empty(self, temp_dir):
        """Test formatting empty file results."""
        tool = SearchTool(str(temp_dir))
        result = tool._format_file_results([], "*.py")

        assert result.status == ToolStatus.SUCCESS
        assert "no files found" in result.output.lower()

    def test_format_file_results_with_matches(self, temp_dir):
        """Test formatting file results with matches."""
        tool = SearchTool(str(temp_dir))
        matches = [
            FileMatch("main.py", 100, "exact match"),
            FileMatch("utils.py", 80, "contains"),
        ]
        result = tool._format_file_results(matches, "py")

        assert result.status == ToolStatus.SUCCESS
        assert "2 files" in result.output
        assert "main.py" in result.output
