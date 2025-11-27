"""File system indexer for Synod - Fast codebase indexing with ripgrep.

This module handles:
- Fast file discovery with ripgrep
- Project statistics and analysis
- Permission management
- Smart context suggestions
"""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
import json

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.tree import Tree

from .theme import PRIMARY, CYAN, GREEN, GOLD, emoji, SynodStyles
from .display import console

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ProjectStats:
    """Statistics about a project."""

    total_files: int = 0
    files_by_type: Dict[str, int] = field(default_factory=dict)
    total_size: int = 0  # in bytes
    languages: Set[str] = field(default_factory=set)

    def add_file(self, file_path: str, size: int = 0) -> None:
        """Add a file to statistics."""
        self.total_files += 1
        self.total_size += size

        # Detect language by extension
        ext = Path(file_path).suffix.lower()
        if ext:
            self.files_by_type[ext] = self.files_by_type.get(ext, 0) + 1

            # Map extensions to languages
            lang = self._ext_to_language(ext)
            if lang:
                self.languages.add(lang)

    def _ext_to_language(self, ext: str) -> Optional[str]:
        """Map file extension to language name."""
        lang_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript',
            '.jsx': 'JavaScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.go': 'Go',
            '.rs': 'Rust',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.cs': 'C#',
            '.scala': 'Scala',
            '.sh': 'Shell',
            '.bash': 'Shell',
            '.zsh': 'Shell',
        }
        return lang_map.get(ext)

    def get_top_languages(self, n: int = 5) -> List[tuple]:
        """Get top N languages by file count."""
        lang_counts = {}
        for ext, count in self.files_by_type.items():
            lang = self._ext_to_language(ext)
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + count

        return sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)[:n]

@dataclass
class FileMetadata:
    """Metadata for a single file."""

    path: str
    size: int
    language: Optional[str]
    extension: str
    last_modified: float

@dataclass
class IndexedProject:
    """Represents an indexed project with full file context."""

    path: str
    files: List[str] = field(default_factory=list)
    file_metadata: Dict[str, FileMetadata] = field(default_factory=dict)
    stats: ProjectStats = field(default_factory=ProjectStats)
    indexed_at: float = 0.0
    permission_granted: bool = False

    def get_file_content(self, file_path: str) -> Optional[str]:
        """Load content of a specific file.

        Args:
            file_path: Relative path to file

        Returns:
            File contents or None if error
        """
        try:
            full_path = Path(self.path) / file_path
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None

    def find_files_by_extension(self, extension: str) -> List[str]:
        """Find all files with a specific extension.

        Args:
            extension: File extension (e.g., '.py', '.js')

        Returns:
            List of matching file paths
        """
        return [f for f in self.files if f.endswith(extension)]

    def find_files_by_language(self, language: str) -> List[str]:
        """Find all files of a specific language.

        Args:
            language: Language name (e.g., 'Python', 'JavaScript')

        Returns:
            List of matching file paths
        """
        return [
            path for path, metadata in self.file_metadata.items()
            if metadata.language == language
        ]

    def search_files(self, pattern: str) -> List[str]:
        """Search for files matching a pattern in their path.

        Args:
            pattern: Pattern to search for (case-insensitive)

        Returns:
            List of matching file paths
        """
        pattern_lower = pattern.lower()
        return [f for f in self.files if pattern_lower in f.lower()]

# ============================================================================
# FILE INDEXER
# ============================================================================

class FileIndexer:
    """Fast file indexer using ripgrep."""

    def __init__(self, project_path: str):
        """Initialize indexer for a project.

        Args:
            project_path: Path to project directory
        """
        self.project_path = Path(project_path).resolve()
        self.stats = ProjectStats()
        self.files: List[str] = []
        self.file_metadata: Dict[str, FileMetadata] = {}

        # Permission and index file locations
        self.synod_dir = self.project_path / '.synod'
        self.permission_file = self.synod_dir / 'permission.json'
        self.index_file = self.synod_dir / 'index.json'

    def has_permission(self) -> bool:
        """Check if we have permission to index this directory."""
        if not self.permission_file.exists():
            return False

        try:
            with open(self.permission_file, 'r') as f:
                data = json.load(f)
                return data.get('permission_granted', False)
        except Exception:
            return False

    def grant_permission(self) -> None:
        """Grant permission to index this directory."""
        self.permission_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.permission_file, 'w') as f:
            json.dump({
                'permission_granted': True,
                'project_path': str(self.project_path),
            }, f, indent=2)

    def check_ripgrep_available(self) -> bool:
        """Check if ripgrep is available."""
        try:
            subprocess.run(['rg', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def index_with_ripgrep(self, show_progress: bool = True) -> List[str]:
        """Index files using ripgrep (fast!).

        Args:
            show_progress: Show progress bar during indexing

        Returns:
            List of file paths
        """
        if not self.check_ripgrep_available():
            console.print("[warning]ripgrep not found, falling back to slower method[/warning]")
            return self.index_with_pathlib(show_progress)

        # Use ripgrep to list all files
        # --files: list files
        # --hidden: include hidden files
        # --no-ignore-vcs: don't ignore VCS files (we'll filter manually)
        cmd = [
            'rg',
            '--files',
            '--hidden',
            '--glob', '!.git/',
            '--glob', '!.synod/',
            '--glob', '!node_modules/',
            '--glob', '!__pycache__/',
            '--glob', '!.venv/',
            '--glob', '!venv/',
            '--glob', '!dist/',
            '--glob', '!build/',
            '--glob', '!*.pyc',
            str(self.project_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=self.project_path
            )

            files = result.stdout.strip().split('\n')
            files = [f for f in files if f]  # Remove empty lines

            # Update stats with progress
            if show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(
                        f"[{CYAN}]Analyzing files...[/{CYAN}]",
                        total=len(files)
                    )

                    for file_path in files:
                        full_path = self.project_path / file_path
                        if full_path.exists():
                            stat = full_path.stat()
                            size = stat.st_size
                            ext = Path(file_path).suffix.lower()
                            lang = self.stats._ext_to_language(ext)

                            # Store metadata
                            self.file_metadata[file_path] = FileMetadata(
                                path=file_path,
                                size=size,
                                language=lang,
                                extension=ext,
                                last_modified=stat.st_mtime,
                            )

                            self.stats.add_file(file_path, size)
                            self.files.append(file_path)
                        progress.advance(task)
            else:
                # Just collect stats without progress bar
                for file_path in files:
                    full_path = self.project_path / file_path
                    if full_path.exists():
                        stat = full_path.stat()
                        size = stat.st_size
                        ext = Path(file_path).suffix.lower()
                        lang = self.stats._ext_to_language(ext)

                        # Store metadata
                        self.file_metadata[file_path] = FileMetadata(
                            path=file_path,
                            size=size,
                            language=lang,
                            extension=ext,
                            last_modified=stat.st_mtime,
                        )

                        self.stats.add_file(file_path, size)
                        self.files.append(file_path)

            return self.files

        except subprocess.CalledProcessError as e:
            console.print(f"[error]Error running ripgrep: {e}[/error]")
            return self.index_with_pathlib(show_progress)

    def index_with_pathlib(self, show_progress: bool = True) -> List[str]:
        """Fallback indexer using pathlib (slower).

        Args:
            show_progress: Show progress indicator

        Returns:
            List of file paths
        """
        if show_progress:
            console.print(f"[{CYAN}]Scanning directory...[/{CYAN}]")

        # Directories to skip
        skip_dirs = {'.git', '.synod', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build'}

        for root, dirs, files in os.walk(self.project_path):
            # Remove skip_dirs from dirs to prevent walking into them
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for file in files:
                # Skip certain files
                if file.endswith('.pyc') or file.startswith('.'):
                    continue

                file_path = Path(root) / file
                relative_path = file_path.relative_to(self.project_path)
                relative_path_str = str(relative_path)

                stat = file_path.stat()
                size = stat.st_size
                ext = file_path.suffix.lower()
                lang = self.stats._ext_to_language(ext)

                # Store metadata
                self.file_metadata[relative_path_str] = FileMetadata(
                    path=relative_path_str,
                    size=size,
                    language=lang,
                    extension=ext,
                    last_modified=stat.st_mtime,
                )

                self.stats.add_file(relative_path_str, size)
                self.files.append(relative_path_str)

        return self.files

    def save_index(self) -> None:
        """Save the file index to disk for fast loading."""
        import time
        self.synod_dir.mkdir(parents=True, exist_ok=True)

        # Convert metadata to serializable format
        metadata_dict = {
            path: {
                'path': meta.path,
                'size': meta.size,
                'language': meta.language,
                'extension': meta.extension,
                'last_modified': meta.last_modified,
            }
            for path, meta in self.file_metadata.items()
        }

        index_data = {
            'project_path': str(self.project_path),
            'files': self.files,
            'file_metadata': metadata_dict,
            'total_files': self.stats.total_files,
            'total_size': self.stats.total_size,
            'indexed_at': time.time(),
        }

        with open(self.index_file, 'w') as f:
            json.dump(index_data, f, indent=2)

    def load_index(self) -> bool:
        """Load a previously saved index from disk.

        Returns:
            True if index loaded successfully, False otherwise
        """
        if not self.index_file.exists():
            return False

        try:
            with open(self.index_file, 'r') as f:
                index_data = json.load(f)

            self.files = index_data.get('files', [])

            # Reconstruct metadata objects
            metadata_dict = index_data.get('file_metadata', {})
            self.file_metadata = {
                path: FileMetadata(**meta)
                for path, meta in metadata_dict.items()
            }

            self.stats.total_files = index_data.get('total_files', 0)
            self.stats.total_size = index_data.get('total_size', 0)

            return True
        except Exception:
            return False

    def get_stats_summary(self) -> Table:
        """Generate a beautiful stats summary table."""
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 1),
            collapse_padding=True,
        )
        table.add_column("Label", style="dim", width=20)
        table.add_column("Value", style=f"{CYAN}")

        # Total files
        table.add_row("Total files:", f"{self.stats.total_files:,}")

        # Top languages
        top_langs = self.stats.get_top_languages(3)
        if top_langs:
            langs_str = ", ".join([f"{lang} ({count})" for lang, count in top_langs])
            table.add_row("Languages:", langs_str)

        # Total size (human readable)
        size_mb = self.stats.total_size / (1024 * 1024)
        if size_mb < 1:
            size_str = f"{self.stats.total_size / 1024:.1f} KB"
        else:
            size_str = f"{size_mb:.1f} MB"
        table.add_row("Total size:", size_str)

        return table

# ============================================================================
# PERMISSION PROMPT
# ============================================================================

def show_permission_prompt(indexer: FileIndexer) -> bool:
    """Show permission prompt and get user consent.

    Args:
        indexer: FileIndexer instance with stats

    Returns:
        True if permission granted, False otherwise
    """
    # Quick scan first (no progress)
    indexer.index_with_ripgrep(show_progress=False)

    # Build permission message
    message = Text()
    message.append(f"\n{emoji('project')} Detected project folder\n", style="info")
    message.append(f"   {indexer.project_path}\n\n", style="primary")

    message.append(f"{emoji('warning')}  ", style="warning")
    message.append("Synod needs to index your codebase\n", style="warning")
    message.append("   This enables smart context suggestions\n\n", style="dim")

    message.append("   Analyzing...\n", style="dim")

    # Stats
    top_langs = indexer.stats.get_top_languages(3)
    for lang, count in top_langs:
        message.append(f"   ├─ {lang} files: ", style="dim")
        message.append(f"{count} found\n", style="info")

    message.append(f"   └─ Total: ", style="dim")
    message.append(f"{indexer.stats.total_files} files\n\n", style="info")

    # Panel
    panel = Panel(
        message,
        title=f"[{GOLD}]Permission Required[/{GOLD}]",
        border_style=GOLD,
    )

    console.print(panel)

    # Get user input
    console.print()
    response = console.input("[primary]Grant access? [Y/n]:[/primary] ")
    console.print()

    # Accept Y, y, yes, Yes, or just Enter as yes
    return response.strip().lower() in ['', 'y', 'yes']

# ============================================================================
# QUICK INDEX FUNCTION
# ============================================================================

def is_workspace_indexed(project_path: str) -> bool:
    """
    Check if a workspace has already been indexed.

    Args:
        project_path: Path to project directory

    Returns:
        True if workspace has been indexed before, False otherwise
    """
    project_path = Path(project_path).resolve()

    # Check if index cache exists
    cache_path = project_path / ".synod" / "index.json"
    return cache_path.exists()


def quick_index(project_path: str, force: bool = False) -> Optional[IndexedProject]:
    """Quickly index a project with beautiful output.

    Args:
        project_path: Path to project
        force: Force re-index even if permission exists

    Returns:
        IndexedProject or None if permission denied
    """
    import time
    indexer = FileIndexer(project_path)

    # Check permission
    if not force and indexer.has_permission():
        # Try loading cached index first (fast!)
        if not force and indexer.load_index():
            # Silently loaded from cache - no output needed
            pass
        else:
            # No cache or stale, re-index
            indexer.index_with_ripgrep(show_progress=True)
            # Save index for next time
            indexer.save_index()
    else:
        # Need permission
        if not show_permission_prompt(indexer):
            console.print("\n[warning]Permission denied. Synod will operate without file context.[/warning]\n")
            return None

        # Grant permission
        indexer.grant_permission()

        # Index with progress
        console.print()
        indexer.index_with_ripgrep(show_progress=True)
        console.print()

        # Save index for future use
        indexer.save_index()
        console.print(f"[success]✓ Index saved to {indexer.index_file.relative_to(indexer.project_path)}[/success]\n")

    # Create indexed project with full metadata
    return IndexedProject(
        path=str(indexer.project_path),
        files=indexer.files,
        file_metadata=indexer.file_metadata,
        stats=indexer.stats,
        indexed_at=time.time(),
        permission_granted=True,
    )
