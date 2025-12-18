"""File editor tool for viewing, creating, and editing files."""

import os
import difflib
from typing import Any, Dict, List, Optional

from .base import Tool, ToolResult, ToolStatus, ConfirmationRequired


class FileEditorTool(Tool):
    """View, create, and edit files."""

    name = "file_editor"
    description = """File operations: view, create, and edit files.

Operations:
- view: Read file contents or list directory
- create: Create a new file with content
- str_replace: Replace text in an existing file

For editing, use str_replace with old_str and new_str. The old_str must match exactly."""

    requires_confirmation = True

    # File extensions that are safe to edit (text-based)
    TEXT_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".json",
        ".yaml",
        ".yml",
        ".md",
        ".txt",
        ".html",
        ".css",
        ".scss",
        ".less",
        ".sql",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".rb",
        ".php",
        ".swift",
        ".m",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".gitignore",
        ".dockerfile",
        ".xml",
        ".svg",
        ".vue",
        ".svelte",
        ".astro",
    }

    def __init__(self, working_directory: str, session_flags=None):
        super().__init__(working_directory, session_flags)
        self.edit_history: List[Dict[str, Any]] = []

    def _resolve_path(self, file_path: str) -> str:
        """Resolve file path relative to working directory."""
        if os.path.isabs(file_path):
            return file_path
        return os.path.join(self.working_directory, file_path)

    def _is_text_file(self, file_path: str) -> bool:
        """Check if file is a text file based on extension."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self.TEXT_EXTENSIONS:
            return True
        # Also check files without extensions (like Makefile, Dockerfile)
        basename = os.path.basename(file_path).lower()
        return basename in {
            "makefile",
            "dockerfile",
            "vagrantfile",
            "gemfile",
            "rakefile",
        }

    def _generate_diff(self, old_content: str, new_content: str, file_path: str) -> str:
        """Generate a unified diff between old and new content."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
        return "".join(diff)

    def get_confirmation_info(
        self,
        operation: str,
        file_path: str,
        content: Optional[str] = None,
        old_str: Optional[str] = None,
        new_str: Optional[str] = None,
        **kwargs,
    ) -> Optional[ConfirmationRequired]:
        """Get confirmation info for file operations."""
        # View operations don't need confirmation
        if operation == "view":
            return None

        # Check session flags
        if not self.session_flags.should_confirm("file_ops"):
            return None

        resolved_path = self._resolve_path(file_path)

        if operation == "create":
            preview = (
                content[:500] + "..." if content and len(content) > 500 else content
            )
            return ConfirmationRequired(
                tool_name="file_editor",
                operation="Create file",
                description=f"Create: {resolved_path}",
                details=f"Content preview:\n{preview}",
            )

        elif operation == "str_replace":
            # Generate diff preview
            if os.path.exists(resolved_path):
                try:
                    with open(resolved_path, "r", encoding="utf-8") as f:
                        old_content = f.read()
                    new_content = old_content.replace(old_str, new_str, 1)
                    diff = self._generate_diff(old_content, new_content, file_path)
                except Exception:
                    diff = f"Replace:\n{old_str}\n\nWith:\n{new_str}"
            else:
                diff = f"Replace:\n{old_str}\n\nWith:\n{new_str}"

            return ConfirmationRequired(
                tool_name="file_editor",
                operation="Edit file",
                description=f"Edit: {resolved_path}",
                diff=diff,
            )

        return None

    async def execute(
        self,
        operation: str,
        file_path: str,
        content: Optional[str] = None,
        old_str: Optional[str] = None,
        new_str: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        **kwargs,
    ) -> ToolResult:
        """Execute a file operation.

        Args:
            operation: One of 'view', 'create', 'str_replace'
            file_path: Path to the file (relative or absolute)
            content: Content for create operation
            old_str: String to replace (for str_replace)
            new_str: Replacement string (for str_replace)
            start_line: Starting line for view (1-indexed)
            end_line: Ending line for view (1-indexed)

        Returns:
            ToolResult with operation output
        """
        resolved_path = self._resolve_path(file_path)

        if operation == "view":
            return await self._view(resolved_path, start_line, end_line)
        elif operation == "create":
            return await self._create(resolved_path, content or "")
        elif operation == "str_replace":
            return await self._str_replace(resolved_path, old_str or "", new_str or "")
        else:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=f"Unknown operation: {operation}. Use 'view', 'create', or 'str_replace'",
            )

    async def _view(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> ToolResult:
        """View file contents or list directory."""
        try:
            if os.path.isdir(file_path):
                # List directory
                entries = []
                for entry in sorted(os.listdir(file_path)):
                    full_path = os.path.join(file_path, entry)
                    if os.path.isdir(full_path):
                        entries.append(f"  {entry}/")
                    else:
                        size = os.path.getsize(full_path)
                        entries.append(f"  {entry} ({self._format_size(size)})")

                output = f"Directory: {file_path}\n\n" + "\n".join(entries)
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    output=output,
                    metadata={
                        "type": "directory",
                        "path": file_path,
                        "count": len(entries),
                    },
                )

            if not os.path.exists(file_path):
                return ToolResult(
                    status=ToolStatus.ERROR,
                    output="",
                    error=f"File not found: {file_path}",
                )

            # Read file
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Apply line range if specified
            if start_line is not None or end_line is not None:
                start_idx = (start_line - 1) if start_line else 0
                end_idx = end_line if end_line else total_lines
                start_idx = max(0, start_idx)
                end_idx = min(total_lines, end_idx)
                selected_lines = lines[start_idx:end_idx]
                line_offset = start_idx
            else:
                selected_lines = lines
                line_offset = 0

            # Format with line numbers
            formatted_lines = []
            for i, line in enumerate(selected_lines):
                line_num = line_offset + i + 1
                # Remove trailing newline for display
                line_content = line.rstrip("\n\r")
                formatted_lines.append(f"{line_num:6d}\t{line_content}")

            output = "\n".join(formatted_lines)

            # Add metadata about truncation
            if len(selected_lines) < total_lines:
                output += f"\n\n... Showing lines {line_offset + 1}-{line_offset + len(selected_lines)} of {total_lines}"

            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=output,
                metadata={
                    "type": "file",
                    "path": file_path,
                    "total_lines": total_lines,
                    "shown_lines": len(selected_lines),
                },
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=str(e),
            )

    async def _create(self, file_path: str, content: str) -> ToolResult:
        """Create a new file with content."""
        try:
            # Check if file already exists
            if os.path.exists(file_path):
                return ToolResult(
                    status=ToolStatus.ERROR,
                    output="",
                    error=f"File already exists: {file_path}. Use str_replace to edit existing files.",
                )

            # Create parent directories if needed
            parent_dir = os.path.dirname(file_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            # Write file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Record in history
            self.edit_history.append(
                {
                    "operation": "create",
                    "path": file_path,
                    "content": content,
                }
            )

            line_count = content.count("\n") + 1 if content else 0
            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=f"Created {file_path} ({line_count} lines, {len(content)} bytes)",
                metadata={
                    "path": file_path,
                    "lines": line_count,
                    "bytes": len(content),
                },
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=str(e),
            )

    async def _str_replace(
        self, file_path: str, old_str: str, new_str: str
    ) -> ToolResult:
        """Replace a string in an existing file."""
        try:
            if not os.path.exists(file_path):
                return ToolResult(
                    status=ToolStatus.ERROR,
                    output="",
                    error=f"File not found: {file_path}. Use 'create' to make new files.",
                )

            # Read current content
            with open(file_path, "r", encoding="utf-8") as f:
                old_content = f.read()

            # Check if old_str exists
            if old_str not in old_content:
                # Try fuzzy matching
                fuzzy_result = self._fuzzy_find(old_content, old_str)
                if fuzzy_result:
                    suggestion = f"\n\nDid you mean:\n```\n{fuzzy_result}\n```"
                else:
                    suggestion = ""

                return ToolResult(
                    status=ToolStatus.ERROR,
                    output="",
                    error=f"String not found in file. Make sure old_str matches exactly.{suggestion}",
                    metadata={"path": file_path},
                )

            # Count occurrences
            count = old_content.count(old_str)
            if count > 1:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    output="",
                    error=f"String appears {count} times in file. Add more context to make it unique.",
                    metadata={"path": file_path, "occurrences": count},
                )

            # Perform replacement
            new_content = old_content.replace(old_str, new_str, 1)

            # Save old content for undo
            self.edit_history.append(
                {
                    "operation": "str_replace",
                    "path": file_path,
                    "old_content": old_content,
                    "new_content": new_content,
                }
            )

            # Write new content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # Generate diff for output
            diff = self._generate_diff(
                old_content, new_content, os.path.basename(file_path)
            )

            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=f"Edited {file_path}\n\n{diff}",
                metadata={"path": file_path, "diff": diff},
            )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=str(e),
            )

    def _fuzzy_find(
        self, content: str, search: str, context: int = 50
    ) -> Optional[str]:
        """Try to find a fuzzy match for the search string."""
        lines = content.split("\n")
        search_lines = search.split("\n")

        if not search_lines:
            return None

        # Look for lines that are similar to the first line of search
        first_search = search_lines[0].strip()
        if not first_search:
            return None

        best_match = None
        best_ratio = 0.6  # Minimum similarity threshold

        for i, line in enumerate(lines):
            ratio = difflib.SequenceMatcher(None, line.strip(), first_search).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                # Get context around the match
                start = max(0, i - 1)
                end = min(len(lines), i + len(search_lines) + 1)
                best_match = "\n".join(lines[start:end])

        return best_match

    def _format_size(self, size: int) -> str:
        """Format file size for display."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}" if unit != "B" else f"{size}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["view", "create", "str_replace"],
                    "description": "The operation to perform",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file (relative to working directory or absolute)",
                },
                "content": {
                    "type": "string",
                    "description": "Content for 'create' operation",
                },
                "old_str": {
                    "type": "string",
                    "description": "String to replace (for 'str_replace'). Must match exactly.",
                },
                "new_str": {
                    "type": "string",
                    "description": "Replacement string (for 'str_replace')",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number for 'view' (1-indexed)",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number for 'view' (1-indexed)",
                },
            },
            "required": ["operation", "file_path"],
        }
