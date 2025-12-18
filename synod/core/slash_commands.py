"""Slash command system for Synod interactive mode.

Provides a command palette similar to Claude Code with:
- Slash command registry with extensibility
- Interactive arrow-key selection UI
- Auto-completion when typing /
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, List, Dict, Awaitable, Union, Tuple

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, Window, FormattedTextControl
from prompt_toolkit.styles import Style
from rich.console import Console

from .theme import PRIMARY, CYAN, GRAY


# Type alias for command handlers
CommandHandler = Union[Callable[..., None], Callable[..., Awaitable[None]]]


@dataclass
class SlashCommand:
    """Definition of a slash command."""

    name: str  # Command name without slash (e.g., "exit")
    description: str  # Short description shown in menu
    handler: Optional[CommandHandler] = None  # Function to call when selected
    aliases: List[str] = field(default_factory=list)  # Alternative names
    category: str = "general"  # For grouping in menu
    hidden: bool = False  # If True, don't show in menu but still works

    @property
    def display_name(self) -> str:
        """Get display name with aliases."""
        if self.aliases:
            return f"/{self.name} ({', '.join(self.aliases)})"
        return f"/{self.name}"


class SlashCommandRegistry:
    """Registry for all available slash commands."""

    def __init__(self):
        self._commands: Dict[str, SlashCommand] = {}
        self._aliases: Dict[str, str] = {}  # alias -> command name

    def register(
        self,
        name: str,
        description: str,
        handler: Optional[CommandHandler] = None,
        aliases: Optional[List[str]] = None,
        category: str = "general",
        hidden: bool = False,
    ) -> SlashCommand:
        """Register a new slash command.

        Args:
            name: Command name without slash
            description: Short description
            handler: Function to call (can be async)
            aliases: Alternative names for the command
            category: Category for grouping
            hidden: If True, command works but isn't shown in menu

        Returns:
            The created SlashCommand
        """
        cmd = SlashCommand(
            name=name,
            description=description,
            handler=handler,
            aliases=aliases or [],
            category=category,
            hidden=hidden,
        )

        self._commands[name] = cmd

        # Register aliases
        for alias in cmd.aliases:
            self._aliases[alias] = name

        return cmd

    def get(self, name: str) -> Optional[SlashCommand]:
        """Get a command by name or alias."""
        # Check direct name first
        if name in self._commands:
            return self._commands[name]
        # Check aliases
        if name in self._aliases:
            return self._commands[self._aliases[name]]
        return None

    def get_all(self, include_hidden: bool = False) -> List[SlashCommand]:
        """Get all registered commands."""
        commands = list(self._commands.values())
        if not include_hidden:
            commands = [c for c in commands if not c.hidden]
        return sorted(commands, key=lambda c: c.name)

    def get_by_category(self) -> Dict[str, List[SlashCommand]]:
        """Get commands grouped by category."""
        categories: Dict[str, List[SlashCommand]] = {}
        for cmd in self.get_all():
            if cmd.category not in categories:
                categories[cmd.category] = []
            categories[cmd.category].append(cmd)
        return categories

    def search(self, query: str) -> List[SlashCommand]:
        """Search commands by name or description."""
        query = query.lower()
        results = []
        for cmd in self.get_all():
            if (
                query in cmd.name.lower()
                or query in cmd.description.lower()
                or any(query in alias.lower() for alias in cmd.aliases)
            ):
                results.append(cmd)
        return results


# Global registry instance
_registry = SlashCommandRegistry()


def register_command(
    name: str,
    description: str,
    handler: Optional[CommandHandler] = None,
    aliases: Optional[List[str]] = None,
    category: str = "general",
    hidden: bool = False,
) -> SlashCommand:
    """Register a slash command (convenience function)."""
    return _registry.register(name, description, handler, aliases, category, hidden)


def get_command(name: str) -> Optional[SlashCommand]:
    """Get a command by name or alias."""
    return _registry.get(name)


def get_all_commands() -> List[SlashCommand]:
    """Get all registered commands."""
    return _registry.get_all()


def get_registry() -> SlashCommandRegistry:
    """Get the global registry instance."""
    return _registry


class SlashCommandSelector:
    """Interactive UI for selecting slash commands with arrow keys."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.selected_index = 0
        self.commands: List[SlashCommand] = []
        self.filter_text = ""

    async def show(self, initial_filter: str = "") -> Optional[SlashCommand]:
        """Show the command selector and return the selected command.

        Args:
            initial_filter: Initial filter text (e.g., if user typed "/ex")

        Returns:
            Selected SlashCommand or None if cancelled
        """
        self.filter_text = initial_filter
        self._update_commands()

        if not self.commands:
            return None

        self.selected_index = 0

        # Create key bindings
        kb = KeyBindings()
        result = [None]  # Use list to allow mutation in closure

        @kb.add("up")
        def _(event):
            if self.selected_index > 0:
                self.selected_index -= 1

        @kb.add("down")
        def _(event):
            if self.selected_index < len(self.commands) - 1:
                self.selected_index += 1

        @kb.add("enter")
        def _(event):
            if self.commands:
                result[0] = self.commands[self.selected_index]
            event.app.exit()

        @kb.add("escape")
        @kb.add("c-c")
        def _(event):
            result[0] = None
            event.app.exit()

        @kb.add("backspace")
        def _(event):
            if self.filter_text:
                self.filter_text = self.filter_text[:-1]
                self._update_commands()
                self.selected_index = min(self.selected_index, len(self.commands) - 1)
                if self.selected_index < 0:
                    self.selected_index = 0

        @kb.add(Keys.Any)
        def _(event):
            char = event.data
            if char.isprintable() and char != "/":
                self.filter_text += char
                self._update_commands()
                self.selected_index = 0

        # Create the menu display
        def get_menu_text():
            lines = []

            # Header
            lines.append(("class:header", "  Slash Commands\n"))
            lines.append(
                ("class:dim", "  ─────────────────────────────────────────────────\n")
            )

            if not self.commands:
                lines.append(
                    ("class:dim", f'  No commands matching "/{self.filter_text}"\n')
                )
            else:
                for i, cmd in enumerate(self.commands):
                    if i == self.selected_index:
                        # Selected item
                        lines.append(("class:selected", "  ❯ "))
                        lines.append(("class:selected-name", f"{cmd.display_name:<25}"))
                        lines.append(("class:selected-desc", f" {cmd.description}\n"))
                    else:
                        # Normal item
                        lines.append(("class:normal", "    "))
                        lines.append(("class:name", f"{cmd.display_name:<25}"))
                        lines.append(("class:desc", f" {cmd.description}\n"))

            # Footer with instructions
            lines.append(
                ("class:dim", "  ─────────────────────────────────────────────────\n")
            )
            lines.append(("class:hint", "  ↑↓ navigate  "))
            lines.append(("class:hint", "⏎ select  "))
            lines.append(("class:hint", "esc cancel"))

            return lines

        # Style for the menu
        style = Style.from_dict(
            {
                "header": f"bold {CYAN}",
                "dim": GRAY,
                "selected": f"bold {PRIMARY}",
                "selected-name": f"bold {PRIMARY}",
                "selected-desc": PRIMARY,
                "normal": "",
                "name": CYAN,
                "desc": GRAY,
                "hint": f"{GRAY} italic",
            }
        )

        # Create application
        layout = Layout(
            Window(
                content=FormattedTextControl(get_menu_text),
                always_hide_cursor=True,
            )
        )

        app = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=False,
            mouse_support=False,
        )

        # Run the application
        await app.run_async()

        return result[0]

    def _update_commands(self):
        """Update the filtered command list."""
        if self.filter_text:
            self.commands = _registry.search(self.filter_text)
        else:
            self.commands = _registry.get_all()


async def show_command_selector(initial_filter: str = "") -> Optional[SlashCommand]:
    """Show the command selector UI.

    Args:
        initial_filter: Initial filter text

    Returns:
        Selected SlashCommand or None if cancelled
    """
    selector = SlashCommandSelector()
    return await selector.show(initial_filter)


def parse_slash_command(text: str) -> Tuple[Optional[str], str]:
    """Parse input text for a slash command.

    Args:
        text: User input text

    Returns:
        Tuple of (command_name, remaining_args) or (None, original_text)
    """
    text = text.strip()
    if not text.startswith("/"):
        return None, text

    # Split command from args
    parts = text[1:].split(maxsplit=1)
    if not parts:
        return None, text

    command_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    return command_name, args


# Register default commands
def _register_default_commands():
    """Register the default set of slash commands."""

    # ========== SESSION COMMANDS ==========
    register_command(
        "exit", "Exit the Synod session", aliases=["quit", "q"], category="session"
    )

    register_command("logout", "Logout from Synod Cloud and exit", category="session")

    register_command(
        "clear",
        "Clear conversation history and free up context",
        aliases=["reset", "new"],
        category="session",
    )

    register_command("resume", "Continue a previous session", category="session")

    register_command(
        "cost", "Show the total cost and tokens for this session", category="session"
    )

    register_command("history", "View recent session history", category="session")

    register_command("stats", "Show detailed usage statistics", category="session")

    register_command(
        "compact", "Compact conversation history to save context", category="session"
    )

    register_command(
        "rewind",
        "Undo recent changes and restore checkpoint",
        aliases=["undo"],
        category="session",
    )

    # ========== GIT COMMANDS ==========
    register_command(
        "commit", "Create a commit with AI-generated message", category="git"
    )

    register_command(
        "pr",
        "Create a pull request with debate-synthesized description",
        category="git",
    )

    register_command("diff", "Show and analyze current git changes", category="git")

    # ========== REVIEW COMMANDS ==========
    register_command(
        "review", "Code review mode - critique without changes", category="review"
    )

    register_command(
        "critique", "Run adversarial critique on specific files", category="review"
    )

    # ========== CONFIGURATION COMMANDS ==========
    register_command(
        "config",
        "Open dashboard to manage your account",
        aliases=["settings"],
        category="configuration",
    )

    register_command(
        "bishops", "Open API keys page to configure models", category="configuration"
    )

    register_command(
        "pope", "Open API keys page to configure models", category="configuration"
    )

    register_command(
        "memory",
        "View adversarial memory dashboard and stats",
        category="configuration",
    )

    register_command("hooks", "Configure automation hooks", category="configuration")

    # ========== WORKSPACE COMMANDS ==========
    register_command(
        "search",
        "Intelligent code search with parallel strategies",
        aliases=["find", "grep"],
        category="workspace",
    )

    register_command(
        "context", "View current context usage across all bishops", category="workspace"
    )

    register_command(
        "index",
        "Re-index the current workspace",
        aliases=["reindex"],
        category="workspace",
    )

    register_command(
        "files", "List indexed files in the workspace", category="workspace"
    )

    register_command("add", "Add files to the current context", category="workspace")

    # ========== GENERAL COMMANDS ==========
    register_command(
        "help",
        "Show available commands and keyboard shortcuts",
        aliases=["?"],
        category="general",
    )

    register_command(
        "version", "Show Synod version information", aliases=["v"], category="general"
    )

    register_command(
        "init", "Initialize .synod/SYNOD.md for this project", category="general"
    )


# Initialize default commands on module load
_register_default_commands()
