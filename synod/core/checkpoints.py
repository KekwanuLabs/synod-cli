"""Checkpoint and undo system for Synod.

Provides:
- Auto-checkpoint before file changes
- /rewind command to undo changes
- Git-backed recovery

Similar to Claude Code's checkpoint system.
"""

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Confirm
from rich import box

from .theme import PRIMARY, CYAN, GREEN, GOLD, GRAY, ACCENT

console = Console()


# ============================================================================
# CONSTANTS
# ============================================================================

CHECKPOINTS_DIR = ".synod/checkpoints"
MAX_CHECKPOINTS = 20  # Keep last 20 checkpoints


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class FileBackup:
    """Backup of a single file."""
    path: str
    original_content: Optional[str]  # None if file didn't exist
    existed: bool


@dataclass
class Checkpoint:
    """A checkpoint representing the state before an action."""
    id: str
    timestamp: float
    action: str  # Description of what triggered this checkpoint
    files: List[FileBackup] = field(default_factory=list)
    conversation_index: int = 0  # Index in conversation history

    def to_dict(self) -> Dict[str, Any]:
        """Serialize checkpoint to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action": self.action,
            "files": [
                {
                    "path": f.path,
                    "original_content": f.original_content,
                    "existed": f.existed,
                }
                for f in self.files
            ],
            "conversation_index": self.conversation_index,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """Deserialize checkpoint from dictionary."""
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            action=data["action"],
            files=[
                FileBackup(
                    path=f["path"],
                    original_content=f.get("original_content"),
                    existed=f.get("existed", True),
                )
                for f in data.get("files", [])
            ],
            conversation_index=data.get("conversation_index", 0),
        )


# ============================================================================
# CHECKPOINT MANAGER
# ============================================================================

class CheckpointManager:
    """Manages checkpoints for a project."""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.checkpoints_dir = self.project_path / CHECKPOINTS_DIR
        self._checkpoints: List[Checkpoint] = []
        self._conversation_index = 0

    def _ensure_dir(self) -> None:
        """Ensure checkpoints directory exists."""
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

        # Add to .gitignore if not present
        gitignore = self.project_path / ".synod" / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text()
            if "checkpoints/" not in content:
                with open(gitignore, "a") as f:
                    f.write("\ncheckpoints/\n")
        else:
            gitignore.parent.mkdir(exist_ok=True)
            gitignore.write_text("checkpoints/\nSYNOD.local.md\n")

    def create_checkpoint(
        self,
        action: str,
        files_to_backup: List[str],
    ) -> Checkpoint:
        """Create a new checkpoint before making changes.

        Args:
            action: Description of the action being performed
            files_to_backup: List of file paths that will be modified

        Returns:
            The created Checkpoint
        """
        self._ensure_dir()
        self._conversation_index += 1

        # Generate checkpoint ID
        timestamp = datetime.now().timestamp()
        checkpoint_id = f"{int(timestamp)}_{self._conversation_index}"

        # Backup files
        file_backups = []
        for filepath in files_to_backup:
            full_path = self.project_path / filepath
            backup = FileBackup(
                path=filepath,
                original_content=None,
                existed=full_path.exists(),
            )

            if full_path.exists() and full_path.is_file():
                try:
                    backup.original_content = full_path.read_text(encoding="utf-8")
                except Exception:
                    # Binary file or read error - skip content backup
                    pass

            file_backups.append(backup)

        # Create checkpoint
        checkpoint = Checkpoint(
            id=checkpoint_id,
            timestamp=timestamp,
            action=action,
            files=file_backups,
            conversation_index=self._conversation_index,
        )

        # Save checkpoint
        self._save_checkpoint(checkpoint)
        self._checkpoints.append(checkpoint)

        # Cleanup old checkpoints
        self._cleanup_old_checkpoints()

        return checkpoint

    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to disk."""
        self._ensure_dir()
        filepath = self.checkpoints_dir / f"{checkpoint.id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)

    def _cleanup_old_checkpoints(self) -> None:
        """Remove checkpoints beyond MAX_CHECKPOINTS."""
        checkpoint_files = sorted(self.checkpoints_dir.glob("*.json"), reverse=True)
        for old_file in checkpoint_files[MAX_CHECKPOINTS:]:
            old_file.unlink()

    def get_checkpoints(self, limit: int = 10) -> List[Checkpoint]:
        """Get recent checkpoints.

        Args:
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoints, newest first
        """
        self._ensure_dir()
        checkpoint_files = sorted(self.checkpoints_dir.glob("*.json"), reverse=True)

        checkpoints = []
        for filepath in checkpoint_files[:limit]:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                checkpoints.append(Checkpoint.from_dict(data))
            except Exception:
                continue

        return checkpoints

    def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """Restore files from a checkpoint.

        Args:
            checkpoint_id: ID of the checkpoint to restore

        Returns:
            True if successful
        """
        checkpoint_file = self.checkpoints_dir / f"{checkpoint_id}.json"
        if not checkpoint_file.exists():
            console.print(f"[red]Checkpoint not found: {checkpoint_id}[/red]")
            return False

        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            checkpoint = Checkpoint.from_dict(data)
        except Exception as e:
            console.print(f"[red]Error loading checkpoint: {e}[/red]")
            return False

        # Restore each file
        restored = 0
        for backup in checkpoint.files:
            full_path = self.project_path / backup.path

            if backup.existed and backup.original_content is not None:
                # Restore content
                try:
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(backup.original_content, encoding="utf-8")
                    restored += 1
                except Exception as e:
                    console.print(f"[yellow]Could not restore {backup.path}: {e}[/yellow]")
            elif not backup.existed:
                # File was created, remove it
                if full_path.exists():
                    try:
                        full_path.unlink()
                        restored += 1
                    except Exception as e:
                        console.print(f"[yellow]Could not remove {backup.path}: {e}[/yellow]")

        if restored > 0:
            console.print(f"[green]✓ Restored {restored} file(s) from checkpoint[/green]")
            return True
        else:
            console.print("[yellow]No files to restore[/yellow]")
            return False

    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """Get the most recent checkpoint."""
        checkpoints = self.get_checkpoints(limit=1)
        return checkpoints[0] if checkpoints else None


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_checkpoint_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager(project_path: str = ".") -> CheckpointManager:
    """Get or create the checkpoint manager."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager(project_path)
    return _checkpoint_manager


def reset_checkpoint_manager() -> None:
    """Reset the checkpoint manager."""
    global _checkpoint_manager
    _checkpoint_manager = None


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_checkpoint(action: str, files: List[str]) -> Checkpoint:
    """Create a checkpoint before modifying files."""
    return get_checkpoint_manager().create_checkpoint(action, files)


def restore_latest() -> bool:
    """Restore the most recent checkpoint."""
    manager = get_checkpoint_manager()
    latest = manager.get_latest_checkpoint()
    if latest:
        return manager.restore_checkpoint(latest.id)
    console.print("[yellow]No checkpoints available[/yellow]")
    return False


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

async def handle_rewind_command(args: str = "") -> None:
    """Handle /rewind command - restore from checkpoint."""
    manager = get_checkpoint_manager()
    checkpoints = manager.get_checkpoints(limit=10)

    if not checkpoints:
        console.print("[yellow]No checkpoints available[/yellow]")
        console.print("[dim]Checkpoints are created automatically before file changes[/dim]")
        return

    if args.strip():
        # Restore specific checkpoint
        checkpoint_id = args.strip()
        if Confirm.ask(f"Restore checkpoint {checkpoint_id}?", default=True):
            manager.restore_checkpoint(checkpoint_id)
        return

    # Show checkpoint selection
    table = Table(box=box.ROUNDED, show_header=True, header_style=f"bold {CYAN}")
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Time", style=CYAN, width=20)
    table.add_column("Action", style="white", width=40)
    table.add_column("Files", justify="right", style=GOLD, width=8)

    for i, cp in enumerate(checkpoints):
        time_str = datetime.fromtimestamp(cp.timestamp).strftime("%H:%M:%S")
        table.add_row(
            str(i + 1),
            time_str,
            cp.action[:40] + "..." if len(cp.action) > 40 else cp.action,
            str(len(cp.files)),
        )

    console.print(Panel(table, title="[cyan]Available Checkpoints[/cyan]", border_style="cyan"))

    # Simple selection
    console.print("\n[dim]Enter checkpoint number to restore (or 'q' to cancel):[/dim]")
    try:
        from prompt_toolkit import prompt
        selection = prompt("> ").strip()

        if selection.lower() in ["q", "quit", "cancel", ""]:
            console.print("[dim]Cancelled[/dim]")
            return

        idx = int(selection) - 1
        if 0 <= idx < len(checkpoints):
            checkpoint = checkpoints[idx]
            if Confirm.ask(f"Restore to: {checkpoint.action}?", default=True):
                manager.restore_checkpoint(checkpoint.id)
        else:
            console.print("[red]Invalid selection[/red]")

    except (ValueError, KeyboardInterrupt, EOFError):
        console.print("[dim]Cancelled[/dim]")


# ============================================================================
# GIT-BASED RECOVERY
# ============================================================================

def git_stash_changes() -> bool:
    """Stash all current changes."""
    try:
        result = subprocess.run(
            ["git", "stash", "push", "-m", "synod-checkpoint"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def git_stash_pop() -> bool:
    """Pop the latest stash."""
    try:
        result = subprocess.run(
            ["git", "stash", "pop"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def git_restore_file(filepath: str) -> bool:
    """Restore a file from git HEAD."""
    try:
        result = subprocess.run(
            ["git", "checkout", "HEAD", "--", filepath],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
