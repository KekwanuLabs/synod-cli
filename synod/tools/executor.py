"""Tool executor - dispatches and manages tool execution."""

import asyncio
from typing import Any, Dict, List, Optional, Callable, Awaitable
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.prompt import Confirm

from .base import Tool, ToolResult, ToolStatus, ConfirmationRequired, SessionFlags
from .bash import BashTool
from .file_editor import FileEditorTool
from .search import SearchTool


console = Console()


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

        # Check if confirmation is needed
        if tool.requires_confirmation and not skip_confirmation:
            confirmation_info = tool.get_confirmation_info(**parameters)
            if confirmation_info:
                approved = await self.on_confirmation(confirmation_info)
                if not approved:
                    return ToolResult(
                        status=ToolStatus.CANCELLED,
                        output="",
                        error="Operation cancelled by user",
                    )

        # Execute the tool
        try:
            return await tool.execute(**parameters)
        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                output="",
                error=f"Tool execution failed: {str(e)}",
            )

    async def _default_confirmation(self, info: ConfirmationRequired) -> bool:
        """Default confirmation handler using Rich prompts."""
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

        # Prompt for confirmation
        try:
            return Confirm.ask(
                "[yellow]Proceed with this operation?[/yellow]",
                default=True,
            )
        except (KeyboardInterrupt, EOFError):
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
