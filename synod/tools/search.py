"""Search tool for finding text in files and locating files."""

import asyncio
import json
import os
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from .base import Tool, ToolResult, ToolStatus


@dataclass
class SearchMatch:
    """A single search match."""
    file: str
    line: int
    column: int
    text: str


@dataclass
class FileMatch:
    """A file match with relevance score."""
    path: str
    score: int
    reason: str


class SearchTool(Tool):
    """Search for text in files or find files by name."""

    name = "search"
    description = """Search for text in files or find files by name/pattern.

Two modes:
1. text_search: Search for text/regex patterns in file contents (uses ripgrep)
2. file_search: Find files by name pattern (glob or fuzzy match)

Examples:
- Find all TODO comments: text_search with pattern="TODO"
- Find a function definition: text_search with pattern="def my_function"
- Find Python files: file_search with pattern="*.py"
- Find a specific file: file_search with pattern="config" (fuzzy)"""

    requires_confirmation = False

    # Directories to ignore during search
    IGNORE_DIRS = {
        "node_modules", ".git", ".svn", ".hg", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".tox", ".venv", "venv", "env", ".env", "dist", "build",
        ".next", ".nuxt", "target", "vendor", ".cargo", "coverage", ".coverage",
    }

    def __init__(self, working_directory: str, session_flags=None, max_results: int = 50):
        super().__init__(working_directory, session_flags)
        self.max_results = max_results

    async def execute(
        self,
        mode: str,
        pattern: str,
        path: Optional[str] = None,
        case_sensitive: bool = False,
        whole_word: bool = False,
        file_type: Optional[str] = None,
        include_hidden: bool = False,
        max_results: Optional[int] = None,
        **kwargs
    ) -> ToolResult:
        """Execute a search operation.

        Args:
            mode: Either 'text_search' or 'file_search'
            pattern: Search pattern (regex for text, glob/fuzzy for files)
            path: Directory to search in (default: working directory)
            case_sensitive: Case-sensitive search (default: False)
            whole_word: Match whole words only (default: False)
            file_type: Filter by file type (e.g., 'py', 'js', 'ts')
            include_hidden: Include hidden files (default: False)
            max_results: Maximum number of results (default: 50)

        Returns:
            ToolResult with search matches
        """
        search_path = path or self.working_directory
        if not os.path.isabs(search_path):
            search_path = os.path.join(self.working_directory, search_path)

        effective_max = max_results or self.max_results

        if mode == "text_search":
            return await self._text_search(
                pattern, search_path, case_sensitive, whole_word,
                file_type, include_hidden, effective_max
            )
        elif mode == "file_search":
            return await self._file_search(
                pattern, search_path, include_hidden, effective_max
            )
        else:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=f"Unknown mode: {mode}. Use 'text_search' or 'file_search'",
            )

    async def _text_search(
        self,
        pattern: str,
        path: str,
        case_sensitive: bool,
        whole_word: bool,
        file_type: Optional[str],
        include_hidden: bool,
        max_results: int,
    ) -> ToolResult:
        """Search for text in files using ripgrep or fallback."""
        # Try ripgrep first (fastest)
        rg_result = await self._ripgrep_search(
            pattern, path, case_sensitive, whole_word, file_type, include_hidden, max_results
        )
        if rg_result is not None:
            return rg_result

        # Fallback to Python-based search
        return await self._python_text_search(
            pattern, path, case_sensitive, whole_word, file_type, include_hidden, max_results
        )

    async def _ripgrep_search(
        self,
        pattern: str,
        path: str,
        case_sensitive: bool,
        whole_word: bool,
        file_type: Optional[str],
        include_hidden: bool,
        max_results: int,
    ) -> Optional[ToolResult]:
        """Search using ripgrep (rg) if available."""
        # Build command
        cmd = ["rg", "--json", "--max-count", str(max_results)]

        if not case_sensitive:
            cmd.append("-i")
        if whole_word:
            cmd.append("-w")
        if file_type:
            cmd.extend(["--type", file_type])
        if include_hidden:
            cmd.append("--hidden")

        # Add ignore patterns
        for ignore_dir in self.IGNORE_DIRS:
            cmd.extend(["--glob", f"!{ignore_dir}/**"])

        cmd.extend([pattern, path])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode == 2:
                # rg not found or error
                return None

            # Parse JSON output
            matches = []
            for line in stdout.decode("utf-8", errors="replace").split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        match_data = data["data"]
                        file_path = match_data["path"]["text"]
                        # Make path relative
                        if file_path.startswith(path):
                            file_path = os.path.relpath(file_path, path)
                        for submatch in match_data.get("submatches", []):
                            matches.append(SearchMatch(
                                file=file_path,
                                line=match_data["line_number"],
                                column=submatch.get("start", 0) + 1,
                                text=match_data["lines"]["text"].rstrip(),
                            ))
                except json.JSONDecodeError:
                    continue

            return self._format_text_results(matches, pattern, max_results)

        except FileNotFoundError:
            return None  # rg not installed
        except asyncio.TimeoutError:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error="Search timed out after 30 seconds",
            )
        except Exception:
            return None

    async def _python_text_search(
        self,
        pattern: str,
        path: str,
        case_sensitive: bool,
        whole_word: bool,
        file_type: Optional[str],
        include_hidden: bool,
        max_results: int,
    ) -> ToolResult:
        """Fallback Python-based text search."""
        import re

        # Build regex
        flags = 0 if case_sensitive else re.IGNORECASE
        if whole_word:
            pattern = rf"\b{re.escape(pattern)}\b"

        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=f"Invalid regex pattern: {e}",
            )

        matches = []
        files_searched = 0

        for root, dirs, files in os.walk(path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                files = [f for f in files if not f.startswith(".")]

            for filename in files:
                # Filter by type
                if file_type:
                    if not filename.endswith(f".{file_type}"):
                        continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, path)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            for match in regex.finditer(line):
                                matches.append(SearchMatch(
                                    file=rel_path,
                                    line=line_num,
                                    column=match.start() + 1,
                                    text=line.rstrip(),
                                ))
                                if len(matches) >= max_results:
                                    break
                        if len(matches) >= max_results:
                            break
                except (IOError, UnicodeDecodeError):
                    continue

                files_searched += 1
                if len(matches) >= max_results:
                    break

            if len(matches) >= max_results:
                break

        return self._format_text_results(matches, pattern, max_results)

    def _format_text_results(
        self,
        matches: List[SearchMatch],
        pattern: str,
        max_results: int
    ) -> ToolResult:
        """Format text search results."""
        if not matches:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=f"No matches found for: {pattern}",
                metadata={"pattern": pattern, "matches": 0},
            )

        # Group by file
        by_file: Dict[str, List[SearchMatch]] = {}
        for match in matches:
            if match.file not in by_file:
                by_file[match.file] = []
            by_file[match.file].append(match)

        # Format output
        lines = [f"Found {len(matches)} matches in {len(by_file)} files:\n"]

        for file_path, file_matches in sorted(by_file.items()):
            lines.append(f"\n{file_path}:")
            for m in file_matches[:10]:  # Limit per file
                # Truncate long lines
                text = m.text[:100] + "..." if len(m.text) > 100 else m.text
                lines.append(f"  {m.line}:{m.column}: {text}")
            if len(file_matches) > 10:
                lines.append(f"  ... and {len(file_matches) - 10} more matches")

        if len(matches) >= max_results:
            lines.append(f"\n(Limited to {max_results} results)")

        return ToolResult(
            status=ToolStatus.SUCCESS,
            output="\n".join(lines),
            metadata={
                "pattern": pattern,
                "matches": len(matches),
                "files": len(by_file),
            },
        )

    async def _file_search(
        self,
        pattern: str,
        path: str,
        include_hidden: bool,
        max_results: int,
    ) -> ToolResult:
        """Search for files by name."""
        matches: List[FileMatch] = []
        is_glob = any(c in pattern for c in "*?[")

        for root, dirs, files in os.walk(path):
            # Limit depth
            depth = root[len(path):].count(os.sep)
            if depth > 10:
                dirs[:] = []
                continue

            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                files = [f for f in files if not f.startswith(".")]

            for filename in files:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, path)

                score, reason = self._score_file_match(filename, rel_path, pattern, is_glob)
                if score > 0:
                    matches.append(FileMatch(path=rel_path, score=score, reason=reason))

            if len(matches) >= max_results * 2:  # Get extra for sorting
                break

        # Sort by score and limit
        matches.sort(key=lambda m: -m.score)
        matches = matches[:max_results]

        return self._format_file_results(matches, pattern)

    def _score_file_match(
        self,
        filename: str,
        rel_path: str,
        pattern: str,
        is_glob: bool
    ) -> Tuple[int, str]:
        """Score a file match against the pattern."""
        if is_glob:
            # Glob matching
            if fnmatch.fnmatch(filename, pattern):
                return 100, "glob match (filename)"
            if fnmatch.fnmatch(rel_path, pattern):
                return 90, "glob match (path)"
            if fnmatch.fnmatch(rel_path, f"**/{pattern}"):
                return 80, "glob match (recursive)"
            return 0, ""

        # Fuzzy matching
        pattern_lower = pattern.lower()
        filename_lower = filename.lower()
        path_lower = rel_path.lower()

        # Exact match
        if filename_lower == pattern_lower:
            return 100, "exact match"

        # Starts with
        if filename_lower.startswith(pattern_lower):
            return 90, "starts with"

        # Contains
        if pattern_lower in filename_lower:
            return 80, "contains in filename"

        if pattern_lower in path_lower:
            return 60, "contains in path"

        # Character sequence match (fuzzy)
        if self._fuzzy_match(filename_lower, pattern_lower):
            return 40, "fuzzy match"

        return 0, ""

    def _fuzzy_match(self, text: str, pattern: str) -> bool:
        """Check if all pattern chars appear in order in text."""
        pattern_idx = 0
        for char in text:
            if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
                pattern_idx += 1
        return pattern_idx == len(pattern)

    def _format_file_results(self, matches: List[FileMatch], pattern: str) -> ToolResult:
        """Format file search results."""
        if not matches:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=f"No files found matching: {pattern}",
                metadata={"pattern": pattern, "matches": 0},
            )

        lines = [f"Found {len(matches)} files:\n"]
        for m in matches:
            lines.append(f"  {m.path} ({m.reason})")

        return ToolResult(
            status=ToolStatus.SUCCESS,
            output="\n".join(lines),
            metadata={"pattern": pattern, "matches": len(matches)},
        )

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["text_search", "file_search"],
                    "description": "Search mode: text_search (search file contents) or file_search (find files by name)",
                },
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex for text_search, glob or fuzzy for file_search)",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: working directory)",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case-sensitive search (default: false)",
                },
                "whole_word": {
                    "type": "boolean",
                    "description": "Match whole words only (default: false)",
                },
                "file_type": {
                    "type": "string",
                    "description": "Filter by file extension (e.g., 'py', 'js', 'ts')",
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files and directories (default: false)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 50)",
                },
            },
            "required": ["mode", "pattern"],
        }
