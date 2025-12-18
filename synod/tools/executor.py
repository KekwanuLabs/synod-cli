"""Tool executor - dispatches and manages tool execution.

Integrates with:
- Hooks system (pre_tool_use, post_tool_use, file_modified)
- Checkpoint system (auto-checkpoint before file modifications)
"""

import asyncio
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
import questionary

from .base import Tool, ToolResult, ToolStatus, ConfirmationRequired, SessionFlags
from .bash import BashTool
from .file_editor import FileEditorTool
from .search import SearchTool


console = Console()

# Lazy imports to avoid circular dependencies
def _get_hook_helpers():
    """Lazily import hook system to avoid circular imports."""
    from synod.core.hooks import run_hooks, HookEvent
    return run_hooks, HookEvent

def _get_checkpoint_helpers():
    """Lazily import checkpoint system to avoid circular imports."""
    from synod.core.checkpoints import create_checkpoint
    return create_checkpoint

# Colors for questionary (matching Synod theme)
CYAN = "#06B6D4"
GREEN = "#10B981"
GOLD = "#FBBF24"

# Session-level auto-approve flag (persists across tool calls in same session)
_session_auto_approve: bool = False


class ConfirmationChoice(Enum):
    """User's choice when prompted for tool confirmation."""
    YES = "yes"           # Approve this one
    YES_TO_ALL = "all"    # Approve this and all future
    NO = "no"             # Decline


def reset_session_auto_approve():
    """Reset the session auto-approve flag. Call at session start."""
    global _session_auto_approve
    _session_auto_approve = False


def is_session_auto_approve() -> bool:
    """Check if session auto-approve is enabled."""
    return _session_auto_approve


def set_session_auto_approve(value: bool = True):
    """Set the session auto-approve flag."""
    global _session_auto_approve
    _session_auto_approve = value


class ToolExecutor:
    """Manages tool registration and execution."""

    def __init__(
        self,
        working_directory: str,
        session_flags: Optional[SessionFlags] = None,
        on_confirmation: Optional[Callable[[ConfirmationRequired], Awaitable[bool]]] = None,
    ):
        """Initialize the tool executor.

        Args:
            working_directory: Base directory for all file operations
            session_flags: Flags controlling confirmation behavior
            on_confirmation: Async callback for user confirmation prompts
        """
        self.working_directory = working_directory
        self.session_flags = session_flags or SessionFlags()
        self.on_confirmation = on_confirmation or self._default_confirmation

        # Initialize tools
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Register the default set of tools."""
        self.register_tool(BashTool(self.working_directory, self.session_flags))
        self.register_tool(FileEditorTool(self.working_directory, self.session_flags))
        self.register_tool(SearchTool(self.working_directory, self.session_flags))

    def register_tool(self, tool: Tool):
        """Register a tool for execution."""
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)

    def get_all_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for all registered tools (for AI)."""
        return [tool.get_tool_definition() for tool in self.tools.values()]

    async def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        skip_confirmation: bool = False,
    ) -> ToolResult:
        """Execute a tool with the given parameters.

        Integrates with hooks system:
        - pre_tool_use: Called before execution (can block)
        - post_tool_use: Called after execution
        - file_modified: Called after file changes

        Also creates checkpoints before file modifications for /rewind.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters to pass to the tool
            skip_confirmation: Skip confirmation prompts

        Returns:
            ToolResult with execution output
        """
        tool = self.tools.get(tool_name)
        if not tool:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=f"Unknown tool: {tool_name}. Available tools: {', '.join(self.tools.keys())}",
            )

        # Run pre_tool_use hooks (can block execution)
        try:
            run_hooks, HookEvent = _get_hook_helpers()
            hook_result = run_hooks(
                HookEvent.PRE_TOOL_USE,
                tool_name=tool_name,
                tool_params=parameters,
                working_directory=self.working_directory,
            )
            if not hook_result.allow:
                return ToolResult(
                    status=ToolStatus.CANCELLED,
                    output="",
                    error=f"Blocked by hook: {hook_result.message or 'pre_tool_use hook returned allow=False'}",
                )
            # Apply any modified parameters from hooks
            if hook_result.modified_params:
                parameters = hook_result.modified_params
        except Exception:
            pass  # Hooks are optional, don't fail if they error

        # Check if confirmation is needed
        # Skip if: explicit skip_confirmation OR session auto-approve is enabled
        should_skip = skip_confirmation or is_session_auto_approve()

        if tool.requires_confirmation and not should_skip:
            confirmation_info = tool.get_confirmation_info(**parameters)
            if confirmation_info:
                approved = await self.on_confirmation(confirmation_info)
                if not approved:
                    return ToolResult(
                        status=ToolStatus.CANCELLED,
                        output="",
                        error="Operation cancelled by user",
                    )

        # Create checkpoint before file modifications
        file_path = self._get_file_path_from_params(tool_name, parameters)
        if file_path and self._is_modifying_operation(tool_name, parameters):
            try:
                create_checkpoint = _get_checkpoint_helpers()
                action = self._describe_action(tool_name, parameters)
                create_checkpoint(action, [file_path])
            except Exception:
                pass  # Checkpoints are optional, don't fail if they error

        # Execute the tool
        try:
            result = await tool.execute(**parameters)

            # Run post_tool_use hooks
            try:
                run_hooks, HookEvent = _get_hook_helpers()
                run_hooks(
                    HookEvent.POST_TOOL_USE,
                    tool_name=tool_name,
                    tool_params=parameters,
                    tool_result=result.output,
                    working_directory=self.working_directory,
                )

                # Run file_modified hook if a file was changed
                if file_path and result.status == ToolStatus.SUCCESS and self._is_modifying_operation(tool_name, parameters):
                    run_hooks(
                        HookEvent.FILE_MODIFIED,
                        tool_name=tool_name,
                        file_path=file_path,
                        working_directory=self.working_directory,
                    )
            except Exception:
                pass  # Hooks are optional

            return result

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=f"Tool execution failed: {str(e)}",
            )

    def _get_file_path_from_params(self, tool_name: str, params: Dict[str, Any]) -> Optional[str]:
        """Extract file path from tool parameters."""
        if tool_name == "file_editor":
            return params.get("file_path")
        elif tool_name == "bash":
            # Could parse command for file redirections, but not reliable
            return None
        return None

    def _is_modifying_operation(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """Check if this operation modifies files."""
        if tool_name == "file_editor":
            operation = params.get("operation", "")
            return operation in ("create", "str_replace")
        elif tool_name == "bash":
            # Bash commands might modify files, but we can't reliably detect
            return False
        return False

    def _describe_action(self, tool_name: str, params: Dict[str, Any]) -> str:
        """Generate a human-readable description of the action."""
        if tool_name == "file_editor":
            operation = params.get("operation", "edit")
            file_path = params.get("file_path", "file")
            return f"{operation} {file_path}"
        elif tool_name == "bash":
            command = params.get("command", "")[:50]
            return f"bash: {command}"
        return f"{tool_name} operation"

    async def _default_confirmation(self, info: ConfirmationRequired) -> bool:
        """Default confirmation handler using arrow-key selection.

        Shows 3 options with arrow-key navigation:
        - Yes: Approve this operation only
        - Yes to all: Approve this and all future operations in this session
        - No: Decline this operation

        Returns:
            True if approved, False if declined
        """
        console.print()

        # Build confirmation panel
        content = Text()
        content.append(f"Operation: ", style="bold")
        content.append(f"{info.operation}\n", style="cyan")
        content.append(f"\n{info.description}\n", style="white")

        if info.details:
            content.append(f"\n{info.details}\n", style="dim")

        if info.diff:
            console.print(Panel(
                content,
                title=f"[yellow]Confirmation Required[/yellow]",
                border_style="yellow",
            ))
            console.print()
            console.print(Panel(
                Syntax(info.diff, "diff", theme="monokai", line_numbers=False),
                title="[cyan]Changes[/cyan]",
                border_style="cyan",
            ))
        else:
            console.print(Panel(
                content,
                title=f"[yellow]Confirmation Required[/yellow]",
                border_style="yellow",
            ))

        console.print()

        # Use questionary for arrow-key selection
        try:
            choice = await questionary.select(
                "Proceed with this operation?",
                choices=[
                    questionary.Choice("Yes", value="yes"),
                    questionary.Choice("Yes to all (don't ask again)", value="all"),
                    questionary.Choice("No", value="no"),
                ],
                style=questionary.Style([
                    ('selected', f'fg:{GREEN} bold'),
                    ('pointer', f'fg:{GREEN} bold'),
                    ('question', f'fg:{GOLD}'),
                    ('highlighted', f'fg:{CYAN}'),
                ])
            ).ask_async()

            if choice == "all":
                # User chose to approve all - set session flag
                set_session_auto_approve(True)
                console.print(f"[{CYAN}]✓ Auto-approving all operations for this session[/{CYAN}]\n")
                return True
            elif choice == "yes":
                return True
            else:  # "no" or None (cancelled)
                console.print("[dim]Operation declined[/dim]\n")
                return False

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Operation cancelled[/dim]\n")
            return False

    def set_auto_approve(self, tool_type: str, value: bool = True):
        """Set auto-approval for a specific tool type."""
        if tool_type == "bash":
            self.session_flags.auto_approve_bash = value
        elif tool_type in ["file", "file_ops", "files"]:
            self.session_flags.auto_approve_file_ops = value
        elif tool_type == "all":
            self.session_flags.auto_approve_all = value

    def get_working_directory(self) -> str:
        """Get the current working directory."""
        # Check if bash tool has changed directory
        bash_tool = self.tools.get("bash")
        if bash_tool and hasattr(bash_tool, 'current_directory'):
            return bash_tool.current_directory
        return self.working_directory

    def update_working_directory(self, new_dir: str):
        """Update working directory for all tools."""
        self.working_directory = new_dir
        for tool in self.tools.values():
            tool.working_directory = new_dir


# Convenience function for single tool execution
async def run_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    working_directory: str,
    skip_confirmation: bool = False,
) -> ToolResult:
    """Execute a single tool call.

    Args:
        tool_name: Name of the tool
        parameters: Tool parameters
        working_directory: Working directory for execution
        skip_confirmation: Skip user confirmation

    Returns:
        ToolResult with execution output
    """
    executor = ToolExecutor(working_directory)
    return await executor.execute(tool_name, parameters, skip_confirmation)
