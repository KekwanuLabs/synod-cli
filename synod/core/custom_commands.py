"""Custom slash commands from .synod/commands/.

Users can create custom slash commands by adding markdown files to:
- .synod/commands/ (project-specific)
- ~/.synod/commands/ (user-level, all projects)

Each .md file becomes a slash command with the filename as the command name.
The file content becomes the prompt that is sent to the debate.

Example:
  .synod/commands/review.md -> /review command
  ~/.synod/commands/explain.md -> /explain command

File format:
  ---
  description: Short description for help menu
  ---
  Your prompt template here. Use $ARGUMENTS for user input.
"""

import re
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .theme import CYAN
from .slash_commands import register_command

console = Console()


# ============================================================================
# CONSTANTS
# ============================================================================

PROJECT_COMMANDS_DIR = ".synod/commands"
USER_COMMANDS_DIR = Path.home() / ".synod" / "commands"


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class CustomCommand:
    """A custom slash command loaded from a file."""

    name: str
    description: str
    prompt_template: str
    file_path: str
    is_user_command: bool  # True if from ~/.synod/commands/

    def render_prompt(self, arguments: str = "") -> str:
        """Render the prompt template with arguments.

        Supports:
        - $ARGUMENTS - All arguments as a single string
        - $1, $2, ... - Individual arguments
        - $FILE - If an argument looks like a file path
        """
        prompt = self.prompt_template

        # Replace $ARGUMENTS with full argument string
        prompt = prompt.replace("$ARGUMENTS", arguments)

        # Split arguments for individual placeholders
        args = arguments.split() if arguments else []

        # Replace $1, $2, etc.
        for i, arg in enumerate(args, 1):
            prompt = prompt.replace(f"${i}", arg)

        # Clear unused placeholders
        prompt = re.sub(r"\$\d+", "", prompt)

        return prompt.strip()


# ============================================================================
# LOADING FUNCTIONS
# ============================================================================


def parse_command_file(filepath: Path) -> Optional[CustomCommand]:
    """Parse a command markdown file.

    File format:
    ---
    description: Short description
    ---
    Prompt template content
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return None

    # Extract frontmatter
    description = ""
    prompt_template = content

    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        prompt_template = frontmatter_match.group(2)

        # Parse description from frontmatter
        desc_match = re.search(r"description:\s*(.+)", frontmatter)
        if desc_match:
            description = desc_match.group(1).strip()

    # Command name from filename (without .md)
    name = filepath.stem.lower()

    if not description:
        # Generate description from first line of prompt
        first_line = prompt_template.split("\n")[0].strip()
        description = first_line[:60] + "..." if len(first_line) > 60 else first_line

    return CustomCommand(
        name=name,
        description=description,
        prompt_template=prompt_template,
        file_path=str(filepath),
        is_user_command=USER_COMMANDS_DIR in filepath.parents
        or filepath.parent == USER_COMMANDS_DIR,
    )


def load_custom_commands(project_path: str = ".") -> List[CustomCommand]:
    """Load all custom commands from config directories.

    Args:
        project_path: Path to the project

    Returns:
        List of CustomCommand objects
    """
    commands = []
    seen_names = set()

    # Load user commands first (lower priority)
    if USER_COMMANDS_DIR.exists():
        for filepath in USER_COMMANDS_DIR.glob("*.md"):
            cmd = parse_command_file(filepath)
            if cmd and cmd.name not in seen_names:
                commands.append(cmd)
                seen_names.add(cmd.name)

    # Load project commands (higher priority, can override user commands)
    project_commands_dir = Path(project_path) / PROJECT_COMMANDS_DIR
    if project_commands_dir.exists():
        for filepath in project_commands_dir.glob("*.md"):
            cmd = parse_command_file(filepath)
            if cmd:
                # Remove any user command with same name
                commands = [c for c in commands if c.name != cmd.name]
                commands.append(cmd)

    return sorted(commands, key=lambda c: c.name)


def register_custom_commands(project_path: str = ".") -> List[CustomCommand]:
    """Load and register custom commands with the slash command registry.

    Args:
        project_path: Path to the project

    Returns:
        List of registered CustomCommand objects
    """
    commands = load_custom_commands(project_path)

    for cmd in commands:
        # Register with the global registry
        # Note: The actual handler is set up in cli.py based on command type
        register_command(
            name=cmd.name,
            description=cmd.description,
            category="custom",
        )

    return commands


# ============================================================================
# COMMAND EXECUTION
# ============================================================================

_custom_commands: Dict[str, CustomCommand] = {}


def get_custom_command(name: str) -> Optional[CustomCommand]:
    """Get a custom command by name."""
    return _custom_commands.get(name)


def initialize_custom_commands(project_path: str = ".") -> None:
    """Initialize and cache custom commands."""
    global _custom_commands
    commands = load_custom_commands(project_path)
    _custom_commands = {cmd.name: cmd for cmd in commands}

    # Register with slash command system
    for cmd in commands:
        register_command(
            name=cmd.name,
            description=f"[custom] {cmd.description}",
            category="custom",
        )


def is_custom_command(name: str) -> bool:
    """Check if a command name is a custom command."""
    return name in _custom_commands


# ============================================================================
# CREATION HELPERS
# ============================================================================

COMMAND_TEMPLATE = """---
description: {description}
---
{prompt}
"""


def create_custom_command(
    name: str,
    description: str,
    prompt: str,
    project_level: bool = True,
) -> Optional[str]:
    """Create a new custom command file.

    Args:
        name: Command name (will be converted to lowercase)
        description: Short description
        prompt: Prompt template
        project_level: If True, create in .synod/commands/, else ~/.synod/commands/

    Returns:
        Path to created file, or None on failure
    """
    name = name.lower().replace(" ", "-")

    if project_level:
        commands_dir = Path(PROJECT_COMMANDS_DIR)
    else:
        commands_dir = USER_COMMANDS_DIR

    commands_dir.mkdir(parents=True, exist_ok=True)

    filepath = commands_dir / f"{name}.md"

    if filepath.exists():
        console.print(f"[yellow]Command already exists: {filepath}[/yellow]")
        return None

    content = COMMAND_TEMPLATE.format(description=description, prompt=prompt)
    filepath.write_text(content, encoding="utf-8")

    console.print(f"[green]✓ Created custom command: /{name}[/green]")
    console.print(f"[dim]Edit: {filepath}[/dim]")

    return str(filepath)


# ============================================================================
# DISPLAY
# ============================================================================


def display_custom_commands() -> None:
    """Display all custom commands."""
    commands = list(_custom_commands.values())

    if not commands:
        console.print("[yellow]No custom commands found[/yellow]")
        console.print("\n[dim]Create custom commands by adding .md files to:[/dim]")
        console.print(f"[dim]  • {PROJECT_COMMANDS_DIR}/ (project)[/dim]")
        console.print(f"[dim]  • {USER_COMMANDS_DIR}/ (user)[/dim]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style=f"bold {CYAN}")
    table.add_column("Command", style=CYAN)
    table.add_column("Description", style="white")
    table.add_column("Source", style="dim")

    for cmd in commands:
        source = "user" if cmd.is_user_command else "project"
        table.add_row(
            f"/{cmd.name}",
            cmd.description[:50] + "..."
            if len(cmd.description) > 50
            else cmd.description,
            source,
        )

    console.print(
        Panel(table, title="[cyan]Custom Commands[/cyan]", border_style="cyan")
    )


# ============================================================================
# EXAMPLE COMMANDS
# ============================================================================

EXAMPLE_COMMANDS = [
    {
        "name": "explain",
        "description": "Explain code in detail",
        "prompt": """Explain this code in detail:

$ARGUMENTS

Provide:
1. What the code does (high-level overview)
2. How it works (step by step)
3. Key concepts used
4. Potential improvements""",
    },
    {
        "name": "test",
        "description": "Generate tests for code",
        "prompt": """Generate comprehensive tests for:

$ARGUMENTS

Requirements:
1. Cover happy path cases
2. Cover edge cases
3. Cover error cases
4. Use appropriate testing framework for the language
5. Include comments explaining each test""",
    },
    {
        "name": "refactor",
        "description": "Suggest refactoring improvements",
        "prompt": """Analyze this code and suggest refactoring improvements:

$ARGUMENTS

Consider:
1. Code readability
2. Performance
3. Maintainability
4. Design patterns
5. SOLID principles""",
    },
    {
        "name": "security",
        "description": "Security audit of code",
        "prompt": """Perform a security audit on:

$ARGUMENTS

Check for:
1. Injection vulnerabilities (SQL, XSS, command)
2. Authentication/authorization issues
3. Data exposure risks
4. Input validation gaps
5. Cryptography misuse
6. OWASP Top 10 vulnerabilities""",
    },
]


def create_example_commands(project_path: str = ".") -> None:
    """Create example custom commands."""
    commands_dir = Path(project_path) / PROJECT_COMMANDS_DIR
    commands_dir.mkdir(parents=True, exist_ok=True)

    for cmd_data in EXAMPLE_COMMANDS:
        filepath = commands_dir / f"{cmd_data['name']}.md"
        if not filepath.exists():
            content = COMMAND_TEMPLATE.format(
                description=cmd_data["description"],
                prompt=cmd_data["prompt"],
            )
            filepath.write_text(content, encoding="utf-8")

    console.print(
        f"[green]✓ Created {len(EXAMPLE_COMMANDS)} example commands in {commands_dir}[/green]"
    )
