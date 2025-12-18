"""
Alternate Screen Buffer Renderer

Provides flicker-free terminal rendering using the alternate screen buffer.
Similar approach to Gemini CLI's rendering engine.
"""

import sys
import signal
import shutil
from typing import Optional, Callable
from rich.console import Console, RenderableType


class AltBufferRenderer:
    """
    Renders content in the terminal's alternate screen buffer.

    This provides:
    - Flicker-free updates (full screen control)
    - Clean scrollback (normal buffer preserved)
    - Proper handling of terminal resize
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console(force_terminal=True)
        self._in_alt_buffer = False
        self._original_sigwinch = None
        self._last_size = (0, 0)
        self._on_resize: Optional[Callable[[], None]] = None

    def enter(self) -> None:
        """Enter alternate screen buffer."""
        if self._in_alt_buffer:
            return

        # Save cursor and enter alternate buffer
        sys.stdout.write("\033[?1049h")  # Enter alternate screen
        sys.stdout.write("\033[2J")  # Clear screen
        sys.stdout.write("\033[H")  # Move cursor to top-left
        sys.stdout.flush()

        self._in_alt_buffer = True
        self._last_size = shutil.get_terminal_size()

        # Handle terminal resize
        self._setup_resize_handler()

    def exit(self) -> None:
        """Exit alternate screen buffer, restoring normal terminal."""
        if not self._in_alt_buffer:
            return

        # Restore resize handler
        self._restore_resize_handler()

        # Exit alternate buffer (restores normal screen)
        sys.stdout.write("\033[?1049l")
        sys.stdout.flush()

        self._in_alt_buffer = False

    def clear(self) -> None:
        """Clear the screen and move cursor to top."""
        if not self._in_alt_buffer:
            return
        sys.stdout.write("\033[2J")  # Clear screen
        sys.stdout.write("\033[H")  # Cursor to top-left
        sys.stdout.flush()

    def render(self, content: RenderableType) -> None:
        """Render content to the alternate buffer."""
        if not self._in_alt_buffer:
            return

        # Check for resize
        current_size = shutil.get_terminal_size()
        if current_size != self._last_size:
            self._last_size = current_size
            if self._on_resize:
                self._on_resize()

        # Move cursor to top and render
        sys.stdout.write("\033[H")  # Cursor to top-left
        sys.stdout.flush()

        # Use Rich to render the content
        # We capture to string first, then write directly
        # This gives atomic updates
        with self.console.capture() as capture:
            self.console.print(content, end="")

        output = capture.get()

        # Clear from cursor to end of screen after content
        # This handles cases where new content is shorter
        sys.stdout.write(output)
        sys.stdout.write("\033[J")  # Clear from cursor to end of screen
        sys.stdout.flush()

    def set_resize_handler(self, handler: Callable[[], None]) -> None:
        """Set a callback to be called on terminal resize."""
        self._on_resize = handler

    def _setup_resize_handler(self) -> None:
        """Set up SIGWINCH handler for terminal resize."""
        try:
            self._original_sigwinch = signal.getsignal(signal.SIGWINCH)
            signal.signal(signal.SIGWINCH, self._handle_resize)
        except (AttributeError, ValueError):
            # SIGWINCH not available on this platform
            pass

    def _restore_resize_handler(self) -> None:
        """Restore original SIGWINCH handler."""
        try:
            if self._original_sigwinch is not None:
                signal.signal(signal.SIGWINCH, self._original_sigwinch)
        except (AttributeError, ValueError):
            pass

    def _handle_resize(self, signum, frame) -> None:
        """Handle terminal resize signal."""
        self._last_size = shutil.get_terminal_size()
        if self._on_resize:
            self._on_resize()

    @property
    def is_active(self) -> bool:
        """Check if we're in alternate buffer mode."""
        return self._in_alt_buffer

    @property
    def size(self) -> tuple:
        """Get current terminal size (columns, lines)."""
        return shutil.get_terminal_size()

    def __enter__(self):
        """Context manager entry."""
        self.enter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.exit()
        return False


def print_final_result(console: Console, content: RenderableType) -> None:
    """
    Print the final result to normal terminal buffer.

    Called after exiting alternate buffer to put the final
    synthesis into the user's scrollback history.
    """
    console.print()
    console.print(content)
    console.print()
