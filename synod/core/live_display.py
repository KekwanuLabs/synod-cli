"""Real-time streaming display for Synod debate panels.

Provides a live, responsive grid layout showing:
- Each Bishop's output as it streams in real-time
- Pope's synthesis panel
- Responsive column layout (4/3/2/1 based on terminal width)
- Scrollable content for long outputs
- Status indicators (streaming, waiting, complete)
"""

from rich.layout import Layout
from rich.panel import Panel
from rich.console import Console, Group
from rich.text import Text
from rich.live import Live
from typing import Dict, List, Optional
from collections import defaultdict

from .theme import PRIMARY, CYAN, ACCENT, SECONDARY, GOLD, GREEN, format_model_name


class LiveDebateDisplay:
    """Real-time debate display with streaming panels for each model.

    Features:
    - Responsive grid layout (adapts to terminal width)
    - Real-time streaming updates
    - Status indicators for each model
    - Dedicated Pope synthesis panel
    - Scrollable content

    Usage:
        display = LiveDebateDisplay(bishops=["model1", "model2"], pope="model3")
        with display.start():
            display.update_bishop("model1", "Chunk of text...")
            display.update_pope("Pope's response...")
    """

    def __init__(self, bishops: List[str], pope: str, console: Optional[Console] = None):
        """Initialize live debate display.

        Args:
            bishops: List of Bishop model names
            pope: Pope model name
            console: Rich console instance (creates new if None)
        """
        self.bishops = bishops
        self.pope = pope
        self.console = console or Console()

        # Storage for streamed content
        self.bishop_contents: Dict[str, List[str]] = {b: [] for b in bishops}
        self.pope_content: List[str] = []

        # Status tracking
        self.bishop_status: Dict[str, str] = {b: "waiting" for b in bishops}
        self.pope_status: str = "waiting"

        # Live display instance
        self.live: Optional[Live] = None

        # Create layout
        self.layout = self._create_layout()

        # Initialize panels after layout is created
        for idx, bishop in enumerate(self.bishops):
            self._update_bishop_panel(idx, bishop)
        self._update_pope_panel()

    def _get_grid_columns(self) -> int:
        """Calculate optimal number of columns based on terminal width.

        Returns:
            Number of columns (1-4)
        """
        width = self.console.width

        if width > 160:
            return 4  # Wide screen: 4 columns
        elif width > 120:
            return 3  # Medium: 3 columns
        elif width > 80:
            return 2  # Narrow: 2 columns
        else:
            return 1  # Mobile: 1 column

    def _create_layout(self) -> Layout:
        """Create responsive layout with header, bishop grid, and pope panel.

        Returns:
            Rich Layout object
        """
        # Main layout structure
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="bishops", ratio=3),
            Layout(name="pope", ratio=1),
        )

        # Create header
        header_text = Text()
        header_text.append("🏛️  ", style=GOLD)
        header_text.append("Synod Session in Progress", style=f"bold {PRIMARY}")
        layout["header"].update(Panel(header_text, border_style=PRIMARY))

        # Create bishop grid - use a simpler approach
        num_cols = self._get_grid_columns()
        num_bishops = len(self.bishops)

        if num_bishops == 0:
            layout["bishops"].update(Panel("No bishops configured", style="dim"))
        else:
            # For simplicity, use a single row layout
            # More complex multi-row layouts can be added later
            bishop_layouts = []
            for i in range(num_bishops):
                bishop_layout = Layout(name=f"bishop_{i}", ratio=1)
                bishop_layouts.append(bishop_layout)

            # Split into rows based on columns
            if num_bishops <= num_cols:
                # Single row
                layout["bishops"].split_row(*bishop_layouts)
            else:
                # Multiple rows
                num_rows = (num_bishops + num_cols - 1) // num_cols
                rows = []
                for row_idx in range(num_rows):
                    start_idx = row_idx * num_cols
                    end_idx = min(start_idx + num_cols, num_bishops)
                    row_layouts = bishop_layouts[start_idx:end_idx]

                    row = Layout()
                    row.split_row(*row_layouts)
                    rows.append(row)

                layout["bishops"].split_column(*rows)

        # Don't initialize panels here - do it after layout is assigned
        return layout

    def _get_status_indicator(self, status: str) -> str:
        """Get emoji indicator for status.

        Args:
            status: One of "waiting", "streaming", "complete"

        Returns:
            Emoji string
        """
        if status == "streaming":
            return "⏳"
        elif status == "complete":
            return "✓"
        else:  # waiting
            return "⏸️"

    def _format_model_title(self, model: str, status: str) -> str:
        """Format model name with status indicator.

        Args:
            model: Model name
            status: Current status

        Returns:
            Formatted title string
        """
        indicator = self._get_status_indicator(status)
        model_display = format_model_name(model)
        return f"{indicator} {model_display}"

    def _update_bishop_panel(self, idx: int, bishop: str):
        """Update a bishop's panel with current content.

        Args:
            idx: Bishop index
            bishop: Bishop model name
        """
        content = "".join(self.bishop_contents[bishop])
        status = self.bishop_status[bishop]

        # Show placeholder if no content yet
        if not content:
            if status == "waiting":
                content = "[dim]Waiting to speak...[/dim]"
            elif status == "streaming":
                content = "[dim]Thinking...[/dim]"

        # Create panel with appropriate border color
        border_color = CYAN if status == "streaming" else "dim" if status == "waiting" else GREEN

        panel = Panel(
            content,
            title=self._format_model_title(bishop, status),
            border_style=border_color,
            padding=(1, 2),
        )

        try:
            self.layout[f"bishop_{idx}"].update(panel)
        except KeyError:
            # Layout might not have this bishop slot if grid changed
            pass

    def _update_pope_panel(self):
        """Update the Pope's synthesis panel with current content."""
        content = "".join(self.pope_content)
        status = self.pope_status

        # Show placeholder if no content yet
        if not content:
            if status == "waiting":
                content = "[dim]Observing debate...[/dim]"
            elif status == "streaming":
                content = "[dim]Synthesizing perspectives...[/dim]"

        # Create panel with purple border (Pope's color)
        border_color = ACCENT if status == "streaming" else "dim" if status == "waiting" else SECONDARY

        panel = Panel(
            content,
            title=self._format_model_title(self.pope, status),
            border_style=border_color,
            padding=(1, 2),
        )

        self.layout["pope"].update(panel)

    def update_bishop(self, bishop: str, chunk: str, complete: bool = False):
        """Stream a chunk of text to a bishop's panel.

        Args:
            bishop: Bishop model name
            chunk: Text chunk to append
            complete: Whether this is the final chunk
        """
        if bishop not in self.bishop_contents:
            return

        # Update content
        self.bishop_contents[bishop].append(chunk)

        # Update status
        if complete:
            self.bishop_status[bishop] = "complete"
        elif self.bishop_status[bishop] == "waiting":
            self.bishop_status[bishop] = "streaming"

        # Refresh panel
        idx = self.bishops.index(bishop)
        self._update_bishop_panel(idx, bishop)

        # Refresh live display
        if self.live:
            self.live.refresh()

    def update_pope(self, chunk: str, complete: bool = False):
        """Stream a chunk of text to the Pope's panel.

        Args:
            chunk: Text chunk to append
            complete: Whether this is the final chunk
        """
        # Update content
        self.pope_content.append(chunk)

        # Update status
        if complete:
            self.pope_status = "complete"
        elif self.pope_status == "waiting":
            self.pope_status = "streaming"

        # Refresh panel
        self._update_pope_panel()

        # Refresh live display
        if self.live:
            self.live.refresh()

    def mark_bishop_waiting(self, bishop: str):
        """Mark a bishop as waiting to speak.

        Args:
            bishop: Bishop model name
        """
        if bishop in self.bishop_status:
            self.bishop_status[bishop] = "waiting"
            idx = self.bishops.index(bishop)
            self._update_bishop_panel(idx, bishop)
            if self.live:
                self.live.refresh()

    def mark_pope_waiting(self):
        """Mark the Pope as waiting (observing)."""
        self.pope_status = "waiting"
        self._update_pope_panel()
        if self.live:
            self.live.refresh()

    def start(self):
        """Start the live display.

        Returns:
            Live display context manager
        """
        self.live = Live(
            self.layout,
            console=self.console,
            refresh_per_second=10,
            vertical_overflow="visible",
        )
        return self.live

    def stop(self):
        """Stop the live display."""
        if self.live:
            self.live.stop()
            self.live = None


# Convenience function for quick testing
if __name__ == "__main__":
    import asyncio
    import time

    async def demo():
        """Demo the live debate display."""
        bishops = [
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5.1-chat",
            "deepseek/deepseek-v3.1",
        ]
        pope = "anthropic/claude-opus-4.5"

        display = LiveDebateDisplay(bishops=bishops, pope=pope)

        with display.start():
            # Simulate streaming bishops
            for bishop in bishops:
                await asyncio.sleep(0.5)
                display.update_bishop(bishop, "I think we should ")
                await asyncio.sleep(0.3)
                display.update_bishop(bishop, "use a binary search tree ")
                await asyncio.sleep(0.3)
                display.update_bishop(bishop, "for optimal performance.")
                await asyncio.sleep(0.2)
                display.update_bishop(bishop, "", complete=True)

            await asyncio.sleep(1)

            # Simulate streaming pope
            display.update_pope("After reviewing all proposals, ")
            await asyncio.sleep(0.5)
            display.update_pope("I recommend combining ")
            await asyncio.sleep(0.5)
            display.update_pope("the best elements from each approach.")
            await asyncio.sleep(0.3)
            display.update_pope("", complete=True)

            await asyncio.sleep(2)

    asyncio.run(demo())
