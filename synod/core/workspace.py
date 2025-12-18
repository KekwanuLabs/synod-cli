"""Workspace trust and security management for Synod.

This module handles:
- Workspace trust prompts (like Claude Code)
- Tracking trusted directories
- Security warnings for untrusted workspaces
"""

import os
import json
from pathlib import Path
from rich.console import Console
from rich.text import Text

from .theme import GREEN, CYAN

# Config directory for Synod CLI
CONFIG_DIR = os.path.join(Path.home(), ".synod-cli")

# File to store trusted workspaces
TRUSTED_WORKSPACES_FILE = os.path.join(CONFIG_DIR, "trusted_workspaces.json")

console = Console()


def load_trusted_workspaces() -> set:
    """Load the list of trusted workspace paths."""
    if not os.path.exists(TRUSTED_WORKSPACES_FILE):
        return set()

    try:
        with open(TRUSTED_WORKSPACES_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("trusted_paths", []))
    except Exception:
        return set()


def save_trusted_workspace(workspace_path: str) -> None:
    """Save a workspace as trusted."""
    trusted = load_trusted_workspaces()
    trusted.add(str(Path(workspace_path).resolve()))

    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(TRUSTED_WORKSPACES_FILE, "w") as f:
        json.dump({"trusted_paths": list(trusted)}, f, indent=2)


def is_workspace_trusted(workspace_path: str) -> bool:
    """Check if a workspace is already trusted."""
    trusted = load_trusted_workspaces()
    resolved_path = str(Path(workspace_path).resolve())
    return resolved_path in trusted


async def prompt_workspace_trust(workspace_path: str) -> bool:
    """
    Show workspace trust prompt (Claude Code style) with arrow key selection.

    Returns:
        True if user trusts the workspace, False otherwise
    """
    import questionary

    console.print()
    console.print("─" * 80, style="dim")
    console.print()

    # Workspace header
    workspace_text = Text()
    workspace_text.append(" Accessing workspace:\n\n ", style="bold white")
    workspace_text.append(f"{workspace_path}\n\n", style=f"bold {CYAN}")

    # Security warning
    workspace_text.append(
        " Safety check: Is this a project you created or one you trust? "
        "(Like your own code, a well-known open source project, or work from your team). "
        "If not, take a moment to review what's in this folder first.\n\n",
        style="white",
    )

    # Capabilities
    workspace_text.append(
        " The Council will be able to read, edit, and execute files here.\n\n",
        style="white",
    )

    # Security guide
    workspace_text.append(
        " Learn more: https://github.com/KekwanuLabs/synod-cli#security\n\n",
        style="dim",
    )

    console.print(workspace_text)

    # Use questionary for arrow key selection
    try:
        choice = await questionary.select(
            "",
            choices=["Yes, I trust this workspace", "No, exit"],
            style=questionary.Style(
                [
                    ("selected", f"fg:{GREEN} bold"),
                    ("pointer", f"fg:{GREEN} bold"),
                ]
            ),
        ).ask_async()

        if choice == "Yes, I trust this workspace":
            save_trusted_workspace(workspace_path)
            console.print()
            console.print(f" [{GREEN}]✓[/{GREEN}] Workspace trusted!", style=GREEN)
            console.print()
            return True
        else:
            console.print()
            console.print(
                " [red]✗ Workspace access denied. Exiting for your safety.[/red]"
            )
            console.print()
            return False

    except (KeyboardInterrupt, EOFError):
        console.print()
        console.print(" [red]✗ Cancelled. Exiting for your safety.[/red]")
        console.print()
        return False


async def check_workspace_trust(workspace_path: str) -> bool:
    """
    Check if workspace is trusted, prompt if not.

    Returns:
        True if workspace is trusted (or user just trusted it), False otherwise
    """
    # Check if already trusted
    if is_workspace_trusted(workspace_path):
        return True

    # Prompt user
    return await prompt_workspace_trust(workspace_path)
