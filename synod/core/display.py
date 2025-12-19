"""Synod display module - Beautiful visualizations and launch screens.

This module handles all the visual elements of Synod including:
- ASCII art logo
- Launch screen
- Exit summary
- Progress indicators
- Session statistics
"""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED, DOUBLE
from rich.align import Align
from typing import Dict, Any, Optional, List
import time

from .theme import (
    SYNOD_THEME,
    SynodStyles,
    PRIMARY,
    SECONDARY,
    emoji,
)


def get_version() -> str:
    """Get the current version of Synod from package metadata."""
    try:
        from importlib.metadata import version

        return version("synod-cli")
    except Exception:
        return "0.2.0"  # Fallback


def check_cloud_compatibility(cli_version: str) -> dict:
    """Check CLI compatibility with Synod Cloud API.

    Returns a dict with:
    - compatible: bool - whether CLI can work with API
    - update_available: bool - whether a newer CLI exists
    - api_version: str - the cloud API version
    - min_cli_version: str - minimum CLI version required
    - latest_cli_version: str - latest available CLI version

    Returns empty dict on error.
    """
    import urllib.request
    import json

    try:
        url = "https://api.synod.run/version"
        headers = {"X-Synod-CLI-Version": cli_version}
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return {
                "compatible": data.get("compatible", True),
                "update_available": data.get("update_available", False),
                "api_version": data.get("api_version", "unknown"),
                "min_cli_version": data.get("min_cli_version", "0.0.0"),
                "latest_cli_version": data.get("latest_cli_version", cli_version),
            }
    except Exception:
        return {}  # Fail silently


async def prompt_upgrade_interactive(
    current_version: str,
    required_version: str,
    is_blocking: bool = False,
) -> bool:
    """Show an interactive upgrade prompt with arrow key selection.

    Args:
        current_version: Current CLI version
        required_version: Version to upgrade to
        is_blocking: If True, upgrade is required (incompatible). If False, optional.

    Returns:
        True if user chose to upgrade, False otherwise.
    """
    from prompt_toolkit.key_binding import KeyBindings
    from rich.panel import Panel
    import sys

    console = Console()

    # Determine message based on whether blocking or optional
    if is_blocking:
        title = "[bold red]Upgrade Required[/bold red]"
        message = (
            f"[yellow]Your CLI version ({current_version}) is incompatible with Synod Cloud.[/yellow]\n"
            f"[dim]Minimum required version: {required_version}[/dim]\n\n"
            f"[white]Upgrade now to continue using Synod.[/white]"
        )
    else:
        title = "[yellow]Update Available[/yellow]"
        message = (
            f"[dim]Current version:[/dim] {current_version}\n"
            f"[dim]Latest version:[/dim] [green]{required_version}[/green]\n\n"
            f"[white]Would you like to upgrade?[/white]"
        )

    console.print()
    console.print(
        Panel(
            message,
            title=title,
            border_style="yellow" if not is_blocking else "red",
            width=60,
        )
    )
    console.print()

    # Selection state
    selected = [0]  # 0 = Upgrade, 1 = Skip (if allowed)
    options = ["Upgrade now", "Skip"] if not is_blocking else ["Upgrade now"]

    # Key bindings for arrow selection
    bindings = KeyBindings()

    @bindings.add("up")
    def move_up(event):
        if selected[0] > 0:
            selected[0] -= 1

    @bindings.add("down")
    def move_down(event):
        if selected[0] < len(options) - 1:
            selected[0] += 1

    @bindings.add("enter")
    def confirm(event):
        event.app.exit(result=selected[0])

    @bindings.add("c-c")
    def cancel(event):
        if is_blocking:
            # Must upgrade if blocking
            console.print("[red]Upgrade required to continue. Exiting.[/red]")
            sys.exit(1)
        event.app.exit(result=1)  # Skip

    # Use Rich for display, prompt_toolkit for input
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    def get_formatted_text():
        lines = []
        for i, opt in enumerate(options):
            if i == selected[0]:
                lines.append(("class:selected", f"  › {opt}\n"))
            else:
                lines.append(("class:unselected", f"    {opt}\n"))
        lines.append(("class:hint", "\n  ↑↓ to select, Enter to confirm"))
        return lines

    control = FormattedTextControl(get_formatted_text)
    window = Window(content=control, height=len(options) + 2)
    layout = Layout(window)

    from prompt_toolkit.styles import Style

    style = Style.from_dict(
        {
            "selected": "bold cyan",
            "unselected": "gray",
            "hint": "gray italic",
        }
    )

    app = Application(
        layout=layout, key_bindings=bindings, style=style, full_screen=False
    )

    try:
        # Use run_async() since we're already in an async context
        result = await app.run_async()
        console.print()  # Add spacing after selection

        if result == 0:
            # User chose to upgrade
            return auto_upgrade()
        else:
            return False
    except (KeyboardInterrupt, EOFError):
        if is_blocking:
            console.print("[red]Upgrade required to continue. Exiting.[/red]")
            sys.exit(1)
        return False


def check_for_updates(current_version: str) -> Optional[str]:
    """Check PyPI for newer version. Returns new version string or None.

    This is non-blocking and fails silently to not disrupt the user experience.
    """
    import threading
    import urllib.request
    import json

    result = {"new_version": None}

    def _check():
        try:
            url = "https://pypi.org/pypi/synod-cli/json"
            with urllib.request.urlopen(url, timeout=2) as response:
                data = json.loads(response.read().decode())
                latest = data["info"]["version"]

                # Compare versions (simple string comparison works for semver)
                if latest != current_version:
                    # Parse versions to compare properly
                    def parse_version(v):
                        return tuple(int(x) for x in v.split("."))

                    if parse_version(latest) > parse_version(current_version):
                        result["new_version"] = latest
        except Exception:
            pass  # Fail silently

    # Run in background thread with timeout
    thread = threading.Thread(target=_check, daemon=True)
    thread.start()
    thread.join(timeout=2)  # Wait max 2 seconds

    return result["new_version"]


def show_update_notice(new_version: str, current_version: str) -> None:
    """Display update notification to user."""
    console = Console()
    console.print()
    console.print(
        Panel(
            f"[bold yellow]Update available![/bold yellow] [dim]{current_version}[/dim] → [bold green]{new_version}[/bold green]\n\n"
            f"[white]Run:[/white] [cyan]synod upgrade[/cyan]\n"
            f"[dim]or:[/dim]  [dim]pipx upgrade synod-cli[/dim]",
            border_style="yellow",
            title="[yellow]New Version[/yellow]",
            width=50,
        )
    )


def auto_upgrade() -> bool:
    """Attempt to auto-upgrade synod-cli. Returns True if successful."""
    import subprocess
    import sys

    console = Console()
    console.print("\n[cyan]Upgrading Synod CLI...[/cyan]\n")

    # Try pipx first (preferred for CLI tools)
    try:
        result = subprocess.run(
            ["pipx", "upgrade", "synod-cli"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            console.print("[green]✓ Upgraded successfully via pipx![/green]")
            console.print("[dim]Restart synod to use the new version.[/dim]")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fall back to pip
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "synod-cli"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            console.print("[green]✓ Upgraded successfully via pip![/green]")
            console.print("[dim]Restart synod to use the new version.[/dim]")
            return True
        else:
            console.print(f"[red]Upgrade failed: {result.stderr}[/red]")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        console.print(f"[red]Upgrade failed: {e}[/red]")

    return False


# ============================================================================
# BRANDING - Single source of truth for taglines
# ============================================================================

TAGLINE = "Ancient Councils. Modern Intelligence."
SUBTITLE = "AI models debate. Your code wins."
TAGLINE_FULL = f"{TAGLINE} {SUBTITLE}"


def get_tagline() -> str:
    """Get the primary tagline."""
    return TAGLINE


def get_subtitle() -> str:
    """Get the subtitle/value proposition."""
    return SUBTITLE


def get_tagline_full() -> str:
    """Get the full tagline with subtitle."""
    return TAGLINE_FULL


# Initialize console with theme and force color support
console = Console(theme=SYNOD_THEME, force_terminal=True, color_system="truecolor")

# ============================================================================
# ASCII ART LOGO
# ============================================================================

# Cleaner, more legible logo
SYNOD_LOGO = r"""
 ███████╗██╗   ██╗███╗   ██╗ ██████╗ ██████╗
 ██╔════╝╚██╗ ██╔╝████╗  ██║██╔═══██╗██╔══██╗
 ███████╗ ╚████╔╝ ██╔██╗ ██║██║   ██║██║  ██║
 ╚════██║  ╚██╔╝  ██║╚██╗██║██║   ██║██║  ██║
 ███████║   ██║   ██║ ╚████║╚██████╔╝██████╔╝
 ╚══════╝   ╚═╝   ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝
"""

# Even simpler alternative if needed
SYNOD_LOGO_SIMPLE = r"""
 ███████ ██    ██ ███    ██  ██████  ██████  _
 ██       ██  ██  ████   ██ ██    ██ ██   ██
 ███████   ████   ██ ██  ██ ██    ██ ██   ██
      ██    ██    ██  ██ ██ ██    ██ ██   ██
 ███████    ██    ██   ████  ██████  ██████
"""

# ============================================================================
# LAUNCH SCREEN
# ============================================================================


def animate_logo() -> None:
    """Display animated Synod logo with typewriter effect using raw output."""
    import time
    import os
    import shutil
    import sys

    # Save original stdout and stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        # Restore real stdout temporarily (undo Rich's wrapping)
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        # ANSI escape codes
        ORANGE_BOLD = "\033[1;38;5;208m"  # Bold orange
        RESET = "\033[0m"

        # Get terminal dimensions
        terminal_width = shutil.get_terminal_size().columns

        # Use direct file descriptor writes to bypass ALL buffering
        def write_direct(text):
            """Write directly to raw stdout file descriptor 1."""
            os.write(1, text.encode("utf-8"))

        # Simple approach: just add a newline for spacing and continue from current position
        # Don't try to manipulate screen position - just start fresh from where we are
        write_direct("\n")

        # Get full logo text and split into lines for better centering
        logo_lines = SYNOD_LOGO.strip().split("\n")

        # Print each line with typewriter effect
        for line in logo_lines:
            # Calculate centering
            padding = (terminal_width - len(line)) // 2
            spaces = " " * padding if padding > 0 else ""

            # Print leading spaces
            write_direct(spaces)

            # Typewriter effect for this line with color
            write_direct(ORANGE_BOLD)
            for char in line:
                write_direct(char)
                # Fast timing
                if char == " ":
                    time.sleep(0.001)
                else:
                    time.sleep(0.003)  # Fast but visible

            write_direct(RESET)
            # Newline after each line
            write_direct("\n")
            time.sleep(0.01)  # Quick pause between lines

        # Add tagline and subtitle as part of the animation (no jump later)
        write_direct("\n")

        # Tagline - centered, cyan color
        CYAN_COLOR = "\033[38;5;45m"
        tagline_padding = (terminal_width - len(TAGLINE)) // 2
        write_direct(" " * tagline_padding + CYAN_COLOR + TAGLINE + RESET + "\n")

        # Subtitle - centered, dim
        DIM = "\033[2m"
        subtitle_padding = (terminal_width - len(SUBTITLE)) // 2
        write_direct(" " * subtitle_padding + DIM + SUBTITLE + RESET + "\n")

        time.sleep(0.05)  # Brief pause at end

    finally:
        # Restore Rich's wrapped stdout
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def show_launch_screen(
    version: Optional[str] = None,
    project_path: Optional[str] = None,
    file_count: int = 0,
    bishops: Optional[List[str]] = None,
    pope: Optional[str] = None,
    animate: bool = True,
) -> None:
    """Display the beautiful Synod launch screen.

    Args:
        version: Synod version number
        project_path: Path to current project
        file_count: Number of indexed files
        bishops: List of bishop model names
        pope: Pope model name
        animate: Whether to animate the logo
    """
    if animate:
        animate_logo()
        # Tagline and subtitle already shown by animate_logo()

        # Version (use dynamic version if not provided)
        display_version = version or get_version()
        console.print()
        console.print(Text(f"v{display_version}", style="dim"), justify="center")

        # Project info (if available)
        if project_path or file_count > 0 or (bishops and pope):
            console.print()
            from rich.table import Table

            info_table = Table(
                show_header=False,
                box=None,
                padding=(0, 1),
                collapse_padding=True,
            )
            info_table.add_column("icon", style="info", width=2)
            info_table.add_column("label", style="info", width=10)
            info_table.add_column("value", style="info")

            if project_path:
                info_table.add_row(emoji("project"), "Project:", project_path)
            if file_count > 0:
                info_table.add_row(emoji("files"), "Files:", f"{file_count:,} indexed")
            if bishops and pope:
                bishop_names = [_format_model_name(b) for b in bishops]
                bishop_text = ", ".join(bishop_names)
                info_table.add_row(emoji("bishop"), "Bishops:", bishop_text)
                info_table.add_row(emoji("pope"), "Pope:", _format_model_name(pope))

            console.print(Align.center(info_table))

        console.print()  # Extra spacing

    else:
        # Non-animated version with panel (original behavior)
        console.print()  # Just add spacing

        logo_text = Text(SYNOD_LOGO.strip(), style=f"bold {PRIMARY}")

        # Tagline
        tagline = Text(
            TAGLINE,
            style=SynodStyles.SUBTITLE,
            justify="center",
        )

        # Subtitle
        subtitle = Text(
            SUBTITLE,
            style=SynodStyles.TAGLINE,
            justify="center",
        )

        # Version (use dynamic version if not provided)
        display_version = version or get_version()
        version_text = Text(
            f"v{display_version}",
            style="dim",
            justify="center",
        )

        # Project info table (only if available)
        project_text = None
        if project_path or file_count > 0 or (bishops and pope):
            from rich.table import Table

            info_table = Table(
                show_header=False,
                box=None,
                padding=(0, 1),
                collapse_padding=True,
            )
            info_table.add_column("icon", style="info", width=2)
            info_table.add_column("label", style="info", width=10)
            info_table.add_column("value", style="info")

            if project_path:
                info_table.add_row(emoji("project"), "Project:", project_path)
            if file_count > 0:
                info_table.add_row(emoji("files"), "Files:", f"{file_count:,} indexed")
            if bishops and pope:
                bishop_names = [_format_model_name(b) for b in bishops]
                bishop_text = ", ".join(bishop_names)
                info_table.add_row(emoji("bishop"), "Bishops:", bishop_text)
                info_table.add_row(emoji("pope"), "Pope:", _format_model_name(pope))

            project_text = info_table

        # Build layout with proper alignment
        from rich.console import Group

        # Text elements
        header = Text()
        header.append(logo_text)
        header.append("\n\n", style="dim")
        header.append(tagline)
        header.append("\n", style="dim")
        header.append(subtitle)
        header.append("\n\n", style="dim")
        header.append(version_text)

        # Collect all renderables
        renderables = [Align.center(header)]

        # Add project info table if available
        if project_text:
            renderables.append(Text("\n"))
            renderables.append(Align.center(project_text))

        # Group everything
        content_group = Group(*renderables)

        # Display in a panel
        panel = Panel(
            content_group,
            border_style=PRIMARY,
            box=ROUNDED,
            padding=(1, 2),
        )

        console.print(panel)
        console.print()  # Extra spacing


def _format_model_name(model_id: str) -> str:
    """Format model ID into a readable name.

    Args:
        model_id: Full model ID like "anthropic/claude-3.5-sonnet"

    Returns:
        Short name like "Claude 3.5"
    """
    # Remove provider prefix
    if "/" in model_id:
        model_id = model_id.split("/", 1)[1]

    # Common transformations
    replacements = {
        "claude-3.5-sonnet": "Claude 3.5",
        "claude-sonnet-4": "Claude 4.0",
        "gpt-4o": "GPT-4o",
        "gpt-4": "GPT-4",
        "deepseek-chat": "DeepSeek",
        "gemini-1.5-pro": "Gemini 1.5",
    }

    for pattern, replacement in replacements.items():
        if pattern in model_id.lower():
            return replacement

    # Fallback: capitalize and clean
    return model_id.replace("-", " ").title()


# ============================================================================
# EXIT SUMMARY
# ============================================================================


def show_exit_summary(session_data: Dict[str, Any]) -> None:
    """Display beautiful exit summary with session statistics.

    Args:
        session_data: Dictionary containing session metrics:
            - duration: Session duration in seconds
            - debates: Number of debates held
            - files_modified: Number of files changed
            - bishop_usage: Dict of per-bishop usage
            - total_tokens: Total tokens used
            - total_cost: Total cost in USD
    """
    duration = session_data.get("duration", 0)
    debates = session_data.get("debates", 0)
    files_modified = session_data.get("files_modified", 0)
    bishop_usage = session_data.get("bishop_usage", {})
    total_tokens = session_data.get("total_tokens", 0)
    total_cost = session_data.get("total_cost", 0.0)

    # Format duration
    duration_str = _format_duration(duration)

    # Create summary table with tight spacing
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 1),
        collapse_padding=True,
        expand=False,
    )
    table.add_column("Label", style="dim", width=25)
    table.add_column("Value", style="primary", justify="left")

    # Session info
    table.add_row(f"{emoji('time')} Duration:", duration_str)
    table.add_row(f"{emoji('debate')} Debates Held:", str(debates))
    if files_modified > 0:
        table.add_row(f"{emoji('files')} Files Modified:", str(files_modified))

    table.add_section()

    # Token usage
    table.add_row(f"{emoji('tokens')} Total Tokens:", f"{total_tokens:,}")

    # Per-bishop breakdown
    if bishop_usage:
        for model, usage in bishop_usage.items():
            model_name = _format_model_name(model)
            tokens = usage.get("tokens", 0)
            percentage = usage.get("percentage", 0)
            table.add_row(
                f"  ├─ {model_name}:",
                f"{tokens:,} tokens ({percentage:.1f}%)",
            )

    table.add_section()

    # Cost breakdown
    table.add_row(f"{emoji('cost')} Total Cost:", f"${total_cost:.2f}")

    if bishop_usage:
        for model, usage in bishop_usage.items():
            model_name = _format_model_name(model)
            cost = usage.get("cost", 0)
            table.add_row(f"  ├─ {model_name}:", f"${cost:.2f}")

    # Bishop statistics (if interesting)
    if bishop_usage:
        table.add_section()
        # Find most active bishop
        most_active = max(bishop_usage.items(), key=lambda x: x[1].get("tokens", 0))
        most_active_name = _format_model_name(most_active[0])
        most_active_pct = most_active[1].get("percentage", 0)

        table.add_row(
            f"{emoji('bishop')} Most Active:",
            f"{most_active_name} ({most_active_pct:.1f}%)",
        )

    # Wrap in panel
    title_text = Text()
    title_text.append(emoji("council"), style="primary")
    title_text.append("  SYNOD SESSION COMPLETE  ", style="title")
    title_text.append(emoji("council"), style="primary")

    panel = Panel(
        table,
        title=title_text,
        border_style=SECONDARY,
        box=DOUBLE,
        padding=(1, 2),
    )

    console.print()
    console.print(panel)
    console.print()

    # Farewell message
    farewell = Text(justify="center")
    farewell.append("The synod adjourns. Until next time. ", style=SynodStyles.DIM)
    farewell.append("👋", style=PRIMARY)
    console.print(farewell)
    console.print()


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "2m 34s" or "1h 23m"
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


# ============================================================================
# SESSION INFO PANEL
# ============================================================================


def show_session_panel(session_data: Dict[str, Any]) -> None:
    """Display real-time session information panel.

    Args:
        session_data: Current session metrics
    """
    duration = time.time() - session_data.get("start_time", time.time())
    total_cost = session_data.get("total_cost", 0.0)
    total_tokens = session_data.get("total_tokens", 0)
    max_tokens = session_data.get("max_tokens", 200000)
    context_pct = (total_tokens / max_tokens) * 100 if max_tokens > 0 else 0

    # Create compact info display
    info_text = Text()
    info_text.append(f"{emoji('time')} {_format_duration(duration)}", style="dim")
    info_text.append("  ", style="dim")
    info_text.append(f"{emoji('cost')} ${total_cost:.2f}", style="cost")
    info_text.append("  ", style="dim")
    info_text.append(
        f"{emoji('tokens')} {total_tokens:,} ({context_pct:.0f}%)", style="tokens"
    )

    console.print(info_text)


# ============================================================================
# PERMISSION PROMPT
# ============================================================================


def show_permission_prompt(project_path: str, file_count: int) -> bool:
    """Display file access permission prompt.

    Args:
        project_path: Path to project directory
        file_count: Number of files to be indexed

    Returns:
        True if permission granted, False otherwise
    """
    message = Text()
    message.append(f"\n{emoji('project')} Detected project: ", style="info")
    message.append(project_path, style="primary")
    message.append(f"\n\n{emoji('warning')}  ", style="warning")
    message.append("Synod needs permission to index this folder.\n", style="warning")
    message.append(
        "   This allows bishops to understand your codebase.\n\n", style="dim"
    )
    message.append(f"   Files to index: {file_count:,}\n", style="info")
    message.append("   Respects: ", style="dim")
    message.append(".gitignore, .synodignore\n\n", style="info")

    panel = Panel(
        message, title="Permission Required", border_style="warning", box=ROUNDED
    )

    console.print(panel)

    # Note: Actual input handling should be done in REPL/CLI
    # This just displays the prompt
    return True
