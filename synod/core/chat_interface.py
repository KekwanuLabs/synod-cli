"""Chat-style interface for Synod interactive mode.

Provides a modern chat experience with:
- Bottom-pinned input field
- Multi-line support (Shift+Enter for newline)
- Command history
- Auto-growing text area
- Syntax highlighting
- Keyboard shortcuts
- Slash command autocomplete
"""

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import CompleteStyle
from typing import Optional, List
import asyncio

from .theme import PRIMARY, CYAN, GOLD, GREEN, ACCENT
from .slash_commands import get_all_commands, get_command, SlashCommand


# Custom style for Synod chat interface
SYNOD_CHAT_STYLE = Style.from_dict({
    # Prompt styling
    'prompt': f'{PRIMARY} bold',
    'prompt-arrow': f'{CYAN}',

    # Input area
    'input': '#FFFFFF',
    'input-placeholder': '#6B6B85 italic',

    # Bottom toolbar
    'bottom-toolbar': f'bg:{ACCENT} #FFFFFF',
    'bottom-toolbar.key': 'bg:#7C3AED #FFFFFF bold',
    'bottom-toolbar.text': 'bg:#7C3AED #E0E0E0',

    # Completions
    'completion-menu': 'bg:#2A2A3E #FFFFFF',
    'completion-menu.completion': 'bg:#2A2A3E #FFFFFF',
    'completion-menu.completion.current': 'bg:#FF6B35 #000000 bold',

    # Scrollbar
    'scrollbar.background': 'bg:#1A1A2E',
    'scrollbar.button': 'bg:#FF6B35',
})


def create_keybindings() -> KeyBindings:
    """Create custom keybindings for Synod chat interface."""
    kb = KeyBindings()

    @kb.add('enter')
    def _(event):
        """Submit on Enter (only if not empty and completion menu not open)"""
        buffer = event.current_buffer
        # If completion menu is visible, select the completion
        if event.app.current_buffer.complete_state:
            buffer.complete_state = None
            return
        # Otherwise submit if not empty
        if buffer.text.strip():
            buffer.validate_and_handle()

    @kb.add('/')
    def _(event):
        """When / is typed at the start, insert it and show completions."""
        buffer = event.current_buffer
        buffer.insert_text('/')
        # Only trigger completion if / is at the start of the line
        if buffer.text.strip() == '/':
            buffer.start_completion(select_first=False)

    @kb.add('c-j')  # Ctrl+J (alternative for newline)
    def _(event):
        """Insert newline with Ctrl+J"""
        event.current_buffer.insert_text('\n')

    @kb.add('escape', 'enter')  # Alt/Esc+Enter
    def _(event):
        """Insert newline with Alt+Enter"""
        event.current_buffer.insert_text('\n')

    @kb.add('c-c')  # Ctrl+C
    def _(event):
        """Clear current input on Ctrl+C"""
        event.current_buffer.text = ''

    @kb.add('c-d')  # Ctrl+D
    def _(event):
        """Exit on Ctrl+D"""
        event.app.exit(exception=EOFError)

    return kb


def get_bottom_toolbar() -> HTML:
    """Generate bottom toolbar with helpful hints."""
    return HTML(
        '<b>[Enter]</b> Submit  '
        '<b>[/]</b> Commands  '
        '<b>[↑↓]</b> History  '
        '<b>[Ctrl+C]</b> Clear  '
        '<b>[Ctrl+D]</b> Exit'
    )


class SlashCommandCompleter(Completer):
    """Completer for slash commands that shows a menu when / is typed."""

    def get_completions(self, document, complete_event):
        """Generate completions for slash commands."""
        text = document.text_before_cursor.strip()

        # Only complete if the line starts with /
        if not text.startswith('/'):
            return

        # Get the command being typed (without the /)
        command_text = text[1:].lower()

        # Get all commands and filter
        for cmd in get_all_commands():
            # Check if command matches (or show all if just /)
            if not command_text or cmd.name.startswith(command_text):
                # Calculate what to insert (the rest of the command)
                display = f"/{cmd.name}"
                if cmd.aliases:
                    display += f" ({', '.join(cmd.aliases)})"
                display_meta = cmd.description

                yield Completion(
                    cmd.name,
                    start_position=-len(command_text),
                    display=display,
                    display_meta=display_meta,
                    style='class:completion-command',
                    selected_style='class:completion-command-selected',
                )

            # Also check aliases
            for alias in cmd.aliases:
                if command_text and alias.startswith(command_text) and alias != cmd.name:
                    display = f"/{alias}"
                    display_meta = f"{cmd.description} (→ /{cmd.name})"

                    yield Completion(
                        alias,
                        start_position=-len(command_text),
                        display=display,
                        display_meta=display_meta,
                        style='class:completion-command',
                        selected_style='class:completion-command-selected',
                    )


class SynodChatInterface:
    """Modern chat-style interface for Synod.

    Features:
    - Multi-line input with auto-growing text field
    - Command history with Up/Down navigation
    - Auto-suggestions from history
    - Syntax highlighting
    - Bottom toolbar with shortcuts
    - Pinned to bottom like modern chat apps

    Usage:
        chat = SynodChatInterface()
        user_input = await chat.get_input()
    """

    def __init__(self):
        """Initialize chat interface with prompt-toolkit session."""
        self.history = InMemoryHistory()
        self.completer = SlashCommandCompleter()

        # Create prompt session with all features
        # Note: MULTI_COLUMN shows completions in columns which handles bottom-of-screen better
        self.session = PromptSession(
            message=self._get_prompt_message(),
            multiline=True,
            prompt_continuation=self._get_continuation(),
            style=SYNOD_CHAT_STYLE,
            key_bindings=create_keybindings(),
            history=self.history,
            auto_suggest=AutoSuggestFromHistory(),
            bottom_toolbar=get_bottom_toolbar,
            completer=self.completer,
            complete_while_typing=True,  # Show completions as user types
            complete_style=CompleteStyle.MULTI_COLUMN,  # Multi-column menu handles screen edge better
            reserve_space_for_menu=15,  # Reserve more space for menu
            vi_mode=False,
            mouse_support=False,
            enable_history_search=True,
            wrap_lines=True,
        )

    def _get_prompt_message(self):
        """Get formatted prompt message."""
        return [
            ('class:prompt', 'synod'),
            ('class:prompt-arrow', '> '),
        ]

    def _get_continuation(self):
        """Get continuation prompt for multi-line input."""
        return [
            ('class:prompt-arrow', '... '),
        ]

    async def get_input(self, context_info: Optional[str] = None) -> str:
        """Get user input with chat-style interface.

        Args:
            context_info: Optional context information to display above prompt
                         (e.g., token usage, session status)

        Returns:
            User's input text (stripped of leading/trailing whitespace)

        Raises:
            KeyboardInterrupt: If user presses Ctrl+C on empty input
            EOFError: If user presses Ctrl+D
        """
        try:
            # Get input asynchronously
            user_input = await self.session.prompt_async()

            # Strip whitespace but preserve internal formatting
            return user_input.strip()

        except KeyboardInterrupt:
            # Ctrl+C on empty line - just return empty string
            return ""

        except EOFError:
            # Ctrl+D - propagate to exit
            raise

    def add_to_history(self, text: str):
        """Manually add text to history.

        Useful for adding successful queries to history even if they
        weren't entered through the prompt.

        Args:
            text: Text to add to command history
        """
        self.history.append_string(text)

    def clear_history(self):
        """Clear command history."""
        # InMemoryHistory doesn't have a clear method, so we create a new one
        self.history = InMemoryHistory()
        self.session.history = self.history


# Convenience function for quick usage
async def get_chat_input(context_info: Optional[str] = None) -> str:
    """Convenience function to get chat input without managing session.

    Args:
        context_info: Optional context to display

    Returns:
        User's input text

    Example:
        user_input = await get_chat_input("Context: 50% full")
    """
    chat = SynodChatInterface()
    return await chat.get_input(context_info)
