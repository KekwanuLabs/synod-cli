"""Hooks system for Synod.

Allows automation at various points in the workflow:
- PreToolUse: Before a tool executes
- PostToolUse: After a tool executes
- SessionStart: When a session begins
- SessionEnd: When a session ends
- PreDebate: Before starting a debate
- PostDebate: After debate completes

Similar to Claude Code's hooks system.
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .theme import CYAN, GOLD

console = Console()


# ============================================================================
# HOOK TYPES
# ============================================================================


class HookEvent(Enum):
    """Types of hook events."""

    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PRE_DEBATE = "pre_debate"
    POST_DEBATE = "post_debate"
    FILE_MODIFIED = "file_modified"


@dataclass
class HookContext:
    """Context passed to hooks."""

    event: HookEvent
    tool_name: Optional[str] = None
    tool_params: Optional[Dict[str, Any]] = None
    tool_result: Optional[str] = None
    file_path: Optional[str] = None
    query: Optional[str] = None
    working_directory: str = "."


@dataclass
class HookResult:
    """Result from a hook execution."""

    allow: bool = True  # Whether to continue (for pre-hooks)
    message: Optional[str] = None
    modified_params: Optional[Dict[str, Any]] = None


@dataclass
class Hook:
    """Definition of a hook."""

    name: str
    event: HookEvent
    command: str  # Shell command to run
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "event": self.event.value,
            "command": self.command,
            "enabled": self.enabled,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hook":
        return cls(
            name=data["name"],
            event=HookEvent(data["event"]),
            command=data["command"],
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
        )


# ============================================================================
# HOOKS CONFIGURATION
# ============================================================================

HOOKS_FILE = ".synod/hooks.json"
USER_HOOKS_FILE = Path.home() / ".synod" / "hooks.json"


def load_hooks(project_path: str = ".") -> List[Hook]:
    """Load hooks from config files.

    Loads from:
    1. Project hooks (.synod/hooks.json)
    2. User hooks (~/.synod/hooks.json)
    """
    hooks = []

    # User hooks first (lower priority)
    if USER_HOOKS_FILE.exists():
        try:
            with open(USER_HOOKS_FILE) as f:
                data = json.load(f)
            for hook_data in data.get("hooks", []):
                hooks.append(Hook.from_dict(hook_data))
        except Exception:
            pass

    # Project hooks (higher priority)
    project_hooks_file = Path(project_path) / HOOKS_FILE
    if project_hooks_file.exists():
        try:
            with open(project_hooks_file) as f:
                data = json.load(f)
            for hook_data in data.get("hooks", []):
                hooks.append(Hook.from_dict(hook_data))
        except Exception:
            pass

    return hooks


def save_hooks(hooks: List[Hook], project_path: str = ".") -> None:
    """Save hooks to project config."""
    hooks_file = Path(project_path) / HOOKS_FILE
    hooks_file.parent.mkdir(parents=True, exist_ok=True)

    data = {"hooks": [h.to_dict() for h in hooks]}
    with open(hooks_file, "w") as f:
        json.dump(data, f, indent=2)


# ============================================================================
# HOOK EXECUTION
# ============================================================================


class HookManager:
    """Manages hook registration and execution."""

    def __init__(self, project_path: str = "."):
        self.project_path = project_path
        self.hooks = load_hooks(project_path)

    def get_hooks_for_event(self, event: HookEvent) -> List[Hook]:
        """Get all enabled hooks for an event."""
        return [h for h in self.hooks if h.event == event and h.enabled]

    def execute_hook(self, hook: Hook, context: HookContext) -> HookResult:
        """Execute a single hook.

        Args:
            hook: The hook to execute
            context: Context for the hook

        Returns:
            HookResult with the outcome
        """
        # Build environment with context
        env = os.environ.copy()
        env["SYNOD_EVENT"] = context.event.value
        env["SYNOD_WORKING_DIR"] = context.working_directory

        if context.tool_name:
            env["SYNOD_TOOL"] = context.tool_name
        if context.tool_params:
            env["SYNOD_TOOL_PARAMS"] = json.dumps(context.tool_params)
        if context.tool_result:
            env["SYNOD_TOOL_RESULT"] = context.tool_result[:10000]  # Truncate
        if context.file_path:
            env["SYNOD_FILE"] = context.file_path
        if context.query:
            env["SYNOD_QUERY"] = context.query

        try:
            result = subprocess.run(
                hook.command,
                shell=True,
                cwd=context.working_directory,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )

            # Check exit code
            if result.returncode != 0:
                return HookResult(
                    allow=False,
                    message=result.stderr
                    or f"Hook '{hook.name}' failed with code {result.returncode}",
                )

            # Parse output for any special commands
            output = result.stdout.strip()

            # Look for JSON output for advanced control
            if output.startswith("{"):
                try:
                    hook_output = json.loads(output)
                    return HookResult(
                        allow=hook_output.get("allow", True),
                        message=hook_output.get("message"),
                        modified_params=hook_output.get("params"),
                    )
                except json.JSONDecodeError:
                    pass

            return HookResult(allow=True, message=output if output else None)

        except subprocess.TimeoutExpired:
            return HookResult(allow=True, message=f"Hook '{hook.name}' timed out")
        except Exception as e:
            return HookResult(allow=True, message=f"Hook error: {e}")

    def run_hooks(self, event: HookEvent, context: HookContext) -> HookResult:
        """Run all hooks for an event.

        Args:
            event: The hook event type
            context: Context for the hooks

        Returns:
            Combined HookResult (fails if any hook fails)
        """
        hooks = self.get_hooks_for_event(event)

        for hook in hooks:
            result = self.execute_hook(hook, context)

            if not result.allow:
                return result

            if result.message:
                console.print(f"[dim]Hook '{hook.name}': {result.message}[/dim]")

            if result.modified_params:
                context.tool_params = result.modified_params

        return HookResult(allow=True)

    def add_hook(self, hook: Hook) -> None:
        """Add a new hook."""
        # Remove existing hook with same name
        self.hooks = [h for h in self.hooks if h.name != hook.name]
        self.hooks.append(hook)
        save_hooks(self.hooks, self.project_path)

    def remove_hook(self, name: str) -> bool:
        """Remove a hook by name."""
        original_count = len(self.hooks)
        self.hooks = [h for h in self.hooks if h.name != name]
        if len(self.hooks) < original_count:
            save_hooks(self.hooks, self.project_path)
            return True
        return False


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_hook_manager: Optional[HookManager] = None


def get_hook_manager(project_path: str = ".") -> HookManager:
    """Get or create the hook manager."""
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = HookManager(project_path)
    return _hook_manager


def run_hooks(event: HookEvent, **kwargs) -> HookResult:
    """Convenience function to run hooks."""
    manager = get_hook_manager()
    context = HookContext(event=event, **kwargs)
    return manager.run_hooks(event, context)


# ============================================================================
# COMMAND HANDLERS
# ============================================================================


async def handle_hooks_command(args: str = "") -> None:
    """Handle /hooks command - view and configure hooks."""
    manager = get_hook_manager()

    if not args.strip():
        # List hooks
        if not manager.hooks:
            console.print("[yellow]No hooks configured[/yellow]")
            console.print("\n[dim]Example hooks:[/dim]")
            console.print("[dim]  • Run prettier after file edits[/dim]")
            console.print("[dim]  • Block edits to .env files[/dim]")
            console.print("[dim]  • Run tests after code changes[/dim]")
            console.print("\n[dim]Add hooks to .synod/hooks.json[/dim]")
            return

        table = Table(box=box.ROUNDED, show_header=True, header_style=f"bold {CYAN}")
        table.add_column("Name", style=CYAN)
        table.add_column("Event", style=GOLD)
        table.add_column("Command", style="white")
        table.add_column("Enabled", justify="center")

        for hook in manager.hooks:
            table.add_row(
                hook.name,
                hook.event.value,
                hook.command[:40] + "..." if len(hook.command) > 40 else hook.command,
                "✓" if hook.enabled else "✗",
            )

        console.print(
            Panel(table, title="[cyan]Configured Hooks[/cyan]", border_style="cyan")
        )
        return

    parts = args.strip().split(maxsplit=1)
    action = parts[0].lower()

    if action == "add" and len(parts) > 1:
        # Parse: /hooks add <name> <event> <command>
        hook_parts = parts[1].split(maxsplit=2)
        if len(hook_parts) >= 3:
            name = hook_parts[0]
            try:
                event = HookEvent(hook_parts[1])
            except ValueError:
                console.print(
                    f"[red]Invalid event. Use one of: {', '.join(e.value for e in HookEvent)}[/red]"
                )
                return
            command = hook_parts[2]

            hook = Hook(name=name, event=event, command=command)
            manager.add_hook(hook)
            console.print(f"[green]✓ Added hook '{name}'[/green]")
        else:
            console.print("[yellow]Usage: /hooks add <name> <event> <command>[/yellow]")

    elif action == "remove" and len(parts) > 1:
        name = parts[1]
        if manager.remove_hook(name):
            console.print(f"[green]✓ Removed hook '{name}'[/green]")
        else:
            console.print(f"[yellow]Hook '{name}' not found[/yellow]")

    else:
        console.print("[yellow]Usage:[/yellow]")
        console.print("  /hooks              - List all hooks")
        console.print("  /hooks add <name> <event> <command>")
        console.print("  /hooks remove <name>")
        console.print(f"\n[dim]Events: {', '.join(e.value for e in HookEvent)}[/dim]")


# ============================================================================
# EXAMPLE HOOKS
# ============================================================================

EXAMPLE_HOOKS = [
    Hook(
        name="prettier-format",
        event=HookEvent.POST_TOOL_USE,
        command='if [ "$SYNOD_TOOL" = "file_editor" ] && [[ "$SYNOD_FILE" =~ \\.(ts|tsx|js|jsx)$ ]]; then npx prettier --write "$SYNOD_FILE" 2>/dev/null; fi',
        description="Run prettier on TypeScript/JavaScript files after editing",
    ),
    Hook(
        name="block-env-edits",
        event=HookEvent.PRE_TOOL_USE,
        command='if [ "$SYNOD_TOOL" = "file_editor" ] && [[ "$SYNOD_FILE" =~ \\.env ]]; then echo "{\\"allow\\": false, \\"message\\": \\"Cannot edit .env files\\"}"; fi',
        description="Block edits to .env files",
    ),
    Hook(
        name="run-tests",
        event=HookEvent.POST_DEBATE,
        command="npm test 2>/dev/null || true",
        description="Run tests after each debate",
    ),
]


def create_example_hooks(project_path: str = ".") -> None:
    """Create example hooks configuration."""
    hooks_file = Path(project_path) / HOOKS_FILE
    hooks_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "hooks": [h.to_dict() for h in EXAMPLE_HOOKS],
        "_comment": "Example hooks - modify or remove as needed",
    }

    with open(hooks_file, "w") as f:
        json.dump(data, f, indent=2)

    console.print(f"[green]✓ Created example hooks at {hooks_file}[/green]")
