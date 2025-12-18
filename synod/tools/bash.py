"""Bash tool for executing shell commands."""

import asyncio
import os
import shlex
from typing import Any, Dict, Optional

from .base import Tool, ToolResult, ToolStatus, ConfirmationRequired


class BashTool(Tool):
    """Execute bash commands in the working directory."""

    name = "bash"
    description = """Execute a bash command in the shell.

Use this to:
- Run build commands (npm, pip, cargo, etc.)
- Execute tests
- Run scripts
- Check file contents with cat/head/tail
- Navigate and explore the filesystem
- Run git commands

The command runs in the current working directory. Be careful with destructive commands."""

    requires_confirmation = True

    # Commands that are considered safe (don't need confirmation)
    SAFE_COMMANDS = {
        "ls",
        "pwd",
        "echo",
        "cat",
        "head",
        "tail",
        "wc",
        "find",
        "grep",
        "which",
        "whoami",
        "date",
        "env",
        "printenv",
        "tree",
        "file",
        "git status",
        "git log",
        "git diff",
        "git branch",
        "git remote",
    }

    # Commands that are dangerous and should always be confirmed
    DANGEROUS_PATTERNS = [
        "rm -rf",
        "rm -r",
        "rmdir",
        "sudo",
        "chmod 777",
        "mkfs",
        "dd if=",
        "> /dev/",
        "curl | sh",
        "wget | sh",
    ]

    def __init__(self, working_directory: str, session_flags=None, timeout: int = 120):
        super().__init__(working_directory, session_flags)
        self.timeout = timeout
        self.current_directory = working_directory

    def _is_safe_command(self, command: str) -> bool:
        """Check if command is in the safe list."""
        cmd_lower = command.strip().lower()

        # Check exact matches
        for safe in self.SAFE_COMMANDS:
            if cmd_lower == safe or cmd_lower.startswith(safe + " "):
                return True

        return False

    def _is_dangerous_command(self, command: str) -> bool:
        """Check if command matches dangerous patterns."""
        cmd_lower = command.strip().lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in cmd_lower:
                return True
        return False

    def get_confirmation_info(
        self, command: str, **kwargs
    ) -> Optional[ConfirmationRequired]:
        """Get confirmation info for bash commands."""
        # Safe commands don't need confirmation
        if self._is_safe_command(command):
            return None

        # Check session flags
        if not self.session_flags.should_confirm("bash"):
            return None

        # Build confirmation info
        is_dangerous = self._is_dangerous_command(command)

        return ConfirmationRequired(
            tool_name="bash",
            operation="Execute command" + (" (DANGEROUS)" if is_dangerous else ""),
            description=f"Run: {command}",
            details=f"Working directory: {self.current_directory}",
        )

    async def execute(
        self, command: str, timeout: Optional[int] = None, **kwargs
    ) -> ToolResult:
        """Execute a bash command.

        Args:
            command: The bash command to execute
            timeout: Optional timeout in seconds (default: 120)

        Returns:
            ToolResult with command output
        """
        effective_timeout = timeout or self.timeout

        # Handle cd specially - update internal state
        if command.strip().startswith("cd "):
            return await self._handle_cd(command)

        try:
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.current_directory,
                env={**os.environ, "TERM": "dumb"},  # Disable colors for cleaner output
            )

            try:
                stdout, _ = await asyncio.wait_for(
                    process.communicate(), timeout=effective_timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    status=ToolStatus.ERROR,
                    output="",
                    error=f"Command timed out after {effective_timeout} seconds",
                    metadata={"command": command, "timeout": True},
                )

            output = stdout.decode("utf-8", errors="replace")

            # Truncate if too long (1MB limit)
            max_output = 1024 * 1024
            if len(output) > max_output:
                output = output[:max_output] + "\n... (output truncated)"

            if process.returncode == 0:
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    output=output,
                    metadata={"command": command, "exit_code": 0},
                )
            else:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    output=output,
                    error=f"Command exited with code {process.returncode}",
                    metadata={"command": command, "exit_code": process.returncode},
                )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=str(e),
                metadata={"command": command},
            )

    async def _handle_cd(self, command: str) -> ToolResult:
        """Handle cd command by updating internal directory state."""
        parts = shlex.split(command)
        if len(parts) < 2:
            # cd with no args goes to home
            new_dir = os.path.expanduser("~")
        else:
            target = parts[1]
            if target.startswith("/"):
                new_dir = target
            elif target == "~" or target.startswith("~/"):
                new_dir = os.path.expanduser(target)
            elif target == "..":
                new_dir = os.path.dirname(self.current_directory)
            elif target == ".":
                new_dir = self.current_directory
            else:
                new_dir = os.path.join(self.current_directory, target)

        # Resolve to absolute path
        new_dir = os.path.abspath(new_dir)

        if os.path.isdir(new_dir):
            self.current_directory = new_dir
            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=f"Changed directory to {new_dir}",
                metadata={"command": command, "new_directory": new_dir},
            )
        else:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=f"Directory not found: {new_dir}",
                metadata={"command": command},
            )

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 120)",
                },
            },
            "required": ["command"],
        }
