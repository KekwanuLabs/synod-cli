"""Project context file support for Synod.

Loads project-specific and user-level instructions from:
- .synod/SYNOD.md (project-specific, checked into git)
- .synod/SYNOD.local.md (project-specific, gitignored)
- ~/.synod/SYNOD.md (user-level, applies to all projects)

Similar to Claude Code's CLAUDE.md system.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown

from .theme import PRIMARY, CYAN, GREEN, GOLD, GRAY

console = Console()


# ============================================================================
# CONSTANTS
# ============================================================================

USER_SYNOD_DIR = Path.home() / ".synod"
USER_MEMORY_FILE = USER_SYNOD_DIR / "SYNOD.md"

PROJECT_SYNOD_DIR = ".synod"
PROJECT_MEMORY_FILE = "SYNOD.md"
PROJECT_LOCAL_MEMORY_FILE = "SYNOD.local.md"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ProjectContext:
    """Loaded project context from memory files."""
    user_instructions: str = ""
    project_instructions: str = ""
    local_instructions: str = ""

    # Metadata
    project_path: Optional[str] = None
    user_file_path: Optional[str] = None
    project_file_path: Optional[str] = None
    local_file_path: Optional[str] = None

    @property
    def has_context(self) -> bool:
        """Check if any context was loaded."""
        return bool(self.user_instructions or self.project_instructions or self.local_instructions)

    def get_combined_context(self) -> str:
        """Get all context combined for the AI prompt."""
        parts = []

        if self.user_instructions:
            parts.append(f"## User Preferences\n{self.user_instructions}")

        if self.project_instructions:
            parts.append(f"## Project Guidelines\n{self.project_instructions}")

        if self.local_instructions:
            parts.append(f"## Local Preferences\n{self.local_instructions}")

        return "\n\n".join(parts)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of loaded context."""
        return {
            "user": {
                "loaded": bool(self.user_instructions),
                "path": str(self.user_file_path) if self.user_file_path else None,
                "chars": len(self.user_instructions),
            },
            "project": {
                "loaded": bool(self.project_instructions),
                "path": str(self.project_file_path) if self.project_file_path else None,
                "chars": len(self.project_instructions),
            },
            "local": {
                "loaded": bool(self.local_instructions),
                "path": str(self.local_file_path) if self.local_file_path else None,
                "chars": len(self.local_instructions),
            },
        }


# ============================================================================
# LOADING FUNCTIONS
# ============================================================================

def load_file_if_exists(path: Path) -> Optional[str]:
    """Load a file's contents if it exists."""
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


def load_project_context(project_path: str = ".") -> ProjectContext:
    """Load all project context files.

    Args:
        project_path: Path to the project directory

    Returns:
        ProjectContext with all loaded instructions
    """
    ctx = ProjectContext(project_path=project_path)

    # 1. Load user-level instructions (~/.synod/SYNOD.md)
    user_content = load_file_if_exists(USER_MEMORY_FILE)
    if user_content:
        ctx.user_instructions = user_content
        ctx.user_file_path = str(USER_MEMORY_FILE)

    # 2. Load project-level instructions (.synod/SYNOD.md)
    project_file = Path(project_path) / PROJECT_SYNOD_DIR / PROJECT_MEMORY_FILE
    project_content = load_file_if_exists(project_file)
    if project_content:
        ctx.project_instructions = project_content
        ctx.project_file_path = str(project_file)

    # 3. Load local instructions (.synod/SYNOD.local.md)
    local_file = Path(project_path) / PROJECT_SYNOD_DIR / PROJECT_LOCAL_MEMORY_FILE
    local_content = load_file_if_exists(local_file)
    if local_content:
        ctx.local_instructions = local_content
        ctx.local_file_path = str(local_file)

    return ctx


def find_context_in_hierarchy(start_path: str = ".") -> ProjectContext:
    """Search up the directory tree for context files.

    Looks for .synod/SYNOD.md in parent directories too.
    """
    ctx = ProjectContext(project_path=start_path)
    current = Path(start_path).resolve()

    # Load user-level first
    user_content = load_file_if_exists(USER_MEMORY_FILE)
    if user_content:
        ctx.user_instructions = user_content
        ctx.user_file_path = str(USER_MEMORY_FILE)

    # Search up for project context
    while current != current.parent:
        project_file = current / PROJECT_SYNOD_DIR / PROJECT_MEMORY_FILE
        if project_file.exists():
            content = load_file_if_exists(project_file)
            if content:
                ctx.project_instructions = content
                ctx.project_file_path = str(project_file)
            break
        current = current.parent

    # Local file only in starting directory
    local_file = Path(start_path) / PROJECT_SYNOD_DIR / PROJECT_LOCAL_MEMORY_FILE
    local_content = load_file_if_exists(local_file)
    if local_content:
        ctx.local_instructions = local_content
        ctx.local_file_path = str(local_file)

    return ctx


# ============================================================================
# INITIALIZATION
# ============================================================================

DEFAULT_PROJECT_TEMPLATE = '''# Synod Project Instructions

This file configures how Synod's AI Council works on your project.
It's read automatically when you start a session in this directory.

## Project Overview
<!-- Describe your project here -->

## Code Style
<!-- Preferred coding style, formatting rules -->

## Architecture
<!-- Key architectural decisions, patterns used -->

## Testing
<!-- How to run tests, testing requirements -->

## Important Files
<!-- Key files the AI should know about -->

## Avoid
<!-- Things the AI should NOT do in this project -->
'''

DEFAULT_USER_TEMPLATE = '''# Synod User Preferences

These preferences apply to ALL your Synod sessions.

## Communication Style
<!-- How you prefer the AI to communicate -->

## Code Preferences
<!-- Your general coding preferences -->

## Editor
<!-- Your preferred editor for file opening -->
'''


def init_project_context(project_path: str = ".", force: bool = False) -> Optional[str]:
    """Initialize .synod/SYNOD.md for a project.

    Args:
        project_path: Path to the project
        force: Overwrite existing file

    Returns:
        Path to created file, or None if already exists
    """
    synod_dir = Path(project_path) / PROJECT_SYNOD_DIR
    memory_file = synod_dir / PROJECT_MEMORY_FILE
    gitignore_file = synod_dir / ".gitignore"

    if memory_file.exists() and not force:
        console.print(f"[yellow]Already exists: {memory_file}[/yellow]")
        return None

    # Create directory
    synod_dir.mkdir(exist_ok=True)

    # Write template
    memory_file.write_text(DEFAULT_PROJECT_TEMPLATE, encoding="utf-8")

    # Create .gitignore for local files
    if not gitignore_file.exists():
        gitignore_file.write_text("SYNOD.local.md\ncheckpoints/\n", encoding="utf-8")

    console.print(f"[green]✓ Created {memory_file}[/green]")
    console.print(f"[dim]Edit this file to customize how Synod works on your project[/dim]")

    return str(memory_file)


def init_user_context(force: bool = False) -> Optional[str]:
    """Initialize ~/.synod/SYNOD.md for user preferences.

    Returns:
        Path to created file, or None if already exists
    """
    if USER_MEMORY_FILE.exists() and not force:
        console.print(f"[yellow]Already exists: {USER_MEMORY_FILE}[/yellow]")
        return None

    USER_SYNOD_DIR.mkdir(exist_ok=True)
    USER_MEMORY_FILE.write_text(DEFAULT_USER_TEMPLATE, encoding="utf-8")

    console.print(f"[green]✓ Created {USER_MEMORY_FILE}[/green]")
    return str(USER_MEMORY_FILE)


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

async def handle_init_command(args: str = "") -> None:
    """Handle /init command - initialize project context file."""
    force = "--force" in args or "-f" in args

    filepath = init_project_context(force=force)

    if filepath:
        console.print(Panel(
            "[cyan]Tips for your SYNOD.md:[/cyan]\n\n"
            "• Describe your project's purpose\n"
            "• Specify coding standards (formatting, naming)\n"
            "• List key files and their purposes\n"
            "• Note what the AI should avoid\n"
            "• Include testing instructions",
            title="[green]Project Initialized[/green]",
            border_style="green"
        ))


async def handle_memory_command(args: str = "", api_key: str = None, project_path: str = None) -> None:
    """Handle /memory command - view memory files or cloud adversarial memory.

    Subcommands:
    - /memory           Show cloud memory dashboard (if logged in)
    - /memory show      Show local context files
    - /memory graph     Visualize memory connections (Pro+)
    - /memory timeline  Show memory activity timeline
    - /memory stats     Show detailed memory statistics
    - /memory clear     Clear project memories
    """
    subcommand = args.strip().split()[0] if args.strip() else ""

    # If we have an API key, use cloud memory visualization
    if api_key and subcommand not in ['show', 'local']:
        try:
            from .memory_viz import handle_memory_viz_command
            await handle_memory_viz_command(args, api_key, project_path)
            return
        except ImportError:
            pass  # Fall back to local memory display
        except Exception as e:
            console.print(f"[dim]Cloud memory unavailable: {e}[/dim]")
            # Fall through to local display

    # Show local context files
    ctx = load_project_context()

    if subcommand == "show" or subcommand == "local":
        # Show current memory
        if ctx.has_context:
            console.print(Panel(
                Markdown(ctx.get_combined_context()),
                title="[cyan]Loaded Context[/cyan]",
                border_style="cyan"
            ))
        else:
            console.print("[yellow]No context files found[/yellow]")
            console.print("[dim]Run /init to create .synod/SYNOD.md[/dim]")
        return

    # Show summary of loaded files
    summary = ctx.get_summary()
    text = Text()

    text.append("Local Memory Files\n\n", style=f"bold {CYAN}")

    for name, info in summary.items():
        if info["loaded"]:
            text.append(f"✓ {name}: ", style=GREEN)
            text.append(f"{info['path']} ({info['chars']} chars)\n", style="dim")
        else:
            text.append(f"○ {name}: ", style="dim")
            text.append("not found\n", style="dim")

    console.print(Panel(text, title="[cyan]/memory local[/cyan]", border_style="cyan"))

    # Show cloud memory hint
    if api_key:
        console.print()
        console.print("[dim]Cloud Adversarial Memory: /memory stats | /memory graph | /memory timeline[/dim]")

    # Hint about editing
    if ctx.project_file_path:
        console.print(f"[dim]Edit: {ctx.project_file_path}[/dim]")
    else:
        console.print("[dim]Run /init to create project memory file[/dim]")


def display_context_on_startup(ctx: ProjectContext) -> None:
    """Display loaded context info on session startup."""
    if not ctx.has_context:
        return

    sources = []
    if ctx.user_instructions:
        sources.append("user")
    if ctx.project_instructions:
        sources.append("project")
    if ctx.local_instructions:
        sources.append("local")

    console.print(f"[dim]📝 Loaded context from: {', '.join(sources)}[/dim]")
