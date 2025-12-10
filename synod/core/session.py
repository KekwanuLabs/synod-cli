"""Synod session tracking.

Simplified for thin client - detailed usage tracked in the cloud.
This module tracks local session metrics for display purposes.
"""
import time
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


# ============================================================================
# SESSION STORAGE
# ============================================================================

SESSIONS_DIR = Path.home() / ".synod-cli" / "sessions"


def ensure_sessions_dir() -> Path:
    """Ensure sessions directory exists."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SynodSession:
    """Track a Synod session.

    Note: Detailed usage and pricing is tracked in the cloud.
    This is a simplified local tracker for display purposes.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float = field(default_factory=time.time)
    debates: int = 0
    files_modified: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0  # Only populated for managed mode
    is_managed_mode: bool = False  # Track if user is on managed plan
    total_debate_duration_ms: int = 0  # Actual debate time (not idle time)

    def record_debate(self, duration_ms: int = 0) -> None:
        """Increment debate counter and add debate duration."""
        self.debates += 1
        self.total_debate_duration_ms += duration_ms

    def record_file_modification(self, count: int = 1) -> None:
        """Record file modifications."""
        self.files_modified += count

    def get_duration(self) -> float:
        """Get session duration in seconds."""
        return time.time() - self.start_time

    def get_summary(self) -> Dict[str, Any]:
        """Get session summary for display."""
        return {
            "duration": self.get_duration(),
            "debates": self.debates,
            "files_modified": self.files_modified,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "is_managed_mode": self.is_managed_mode,
            "total_debate_duration_ms": self.total_debate_duration_ms,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "duration": self.get_duration(),
            "debates": self.debates,
            "files_modified": self.files_modified,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "is_managed_mode": self.is_managed_mode,
            "total_debate_duration_ms": self.total_debate_duration_ms,
        }

    def save(self) -> Path:
        """Save session to disk."""
        ensure_sessions_dir()

        date_str = datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d")
        date_dir = SESSIONS_DIR / date_str
        date_dir.mkdir(exist_ok=True)

        timestamp = datetime.fromtimestamp(self.start_time).strftime("%H-%M-%S")
        filename = f"{timestamp}_{self.session_id[:8]}.json"
        filepath = date_dir / filename

        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        return filepath

    @classmethod
    def load(cls, filepath: Path) -> 'SynodSession':
        """Load session from disk."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        return cls(
            session_id=data["session_id"],
            start_time=data["start_time"],
            debates=data["debates"],
            files_modified=data.get("files_modified", 0),
            total_tokens=data.get("total_tokens", 0),
            total_cost=data.get("total_cost", 0.0),
            is_managed_mode=data.get("is_managed_mode", False),
            total_debate_duration_ms=data.get("total_debate_duration_ms", 0),
        )


# ============================================================================
# GLOBAL SESSION INSTANCE
# ============================================================================

_current_session: Optional[SynodSession] = None


def get_current_session() -> SynodSession:
    """Get or create the current session."""
    global _current_session
    if _current_session is None:
        _current_session = SynodSession()
    return _current_session


def reset_session() -> SynodSession:
    """Reset the current session."""
    global _current_session
    _current_session = SynodSession()
    return _current_session


def end_session() -> Dict[str, Any]:
    """End the current session and return summary."""
    session = get_current_session()
    summary = session.get_summary()
    reset_session()
    return summary


# ============================================================================
# DISPLAY HELPER
# ============================================================================

def display_session_summary(session: SynodSession) -> None:
    """Display session summary on exit."""
    from rich.console import Console
    from rich.text import Text
    from rich.panel import Panel
    from rich.box import ROUNDED

    console = Console()

    session_id = session.session_id[:32]

    # Session duration (wall clock time)
    session_duration = session.get_duration()
    session_duration_str = f"{int(session_duration // 60)}m {int(session_duration % 60)}s"

    # Actual debate time (time spent in debates, not idle)
    debate_duration_sec = session.total_debate_duration_ms / 1000
    debate_duration_str = f"{int(debate_duration_sec // 60)}m {int(debate_duration_sec % 60)}s"

    summary = Text()
    summary.append("\n🏛️  Council Dismissed\n\n", style="bold cyan")

    summary.append("Session Summary\n", style="bold")
    summary.append(f"Session ID:     {session_id}\n", style="dim")
    summary.append(f"Debates:        {session.debates}\n", style="dim")
    summary.append(f"Session Time:   {session_duration_str}\n", style="dim")

    # Only show debate time if there were debates
    if session.debates > 0 and session.total_debate_duration_ms > 0:
        summary.append(f"Debate Time:    {debate_duration_str}\n", style="dim")

    summary.append(f"Tokens:         {session.total_tokens:,}\n", style="dim")

    # Show cost differently based on mode
    if session.is_managed_mode:
        summary.append(f"Cost:           ${session.total_cost:.4f}\n\n", style="dim")
    else:
        summary.append(f"Cost:           BYOK (billed to your providers)\n\n", style="dim")

    summary.append("Full usage details at synod.run/dashboard", style="dim")

    console.print(Panel(summary, border_style="cyan", box=ROUNDED))
    console.print()


# ============================================================================
# SESSION HISTORY
# ============================================================================

def get_all_sessions() -> List[Path]:
    """Get all saved session files, sorted by date (newest first)."""
    if not SESSIONS_DIR.exists():
        return []

    sessions = list(SESSIONS_DIR.rglob("*.json"))
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions


def get_recent_sessions(limit: int = 10) -> List[SynodSession]:
    """Get recent sessions."""
    session_files = get_all_sessions()[:limit]

    sessions = []
    for filepath in session_files:
        try:
            sessions.append(SynodSession.load(filepath))
        except Exception:
            continue

    return sessions


def get_session_stats() -> Dict[str, Any]:
    """Get aggregate statistics across all sessions."""
    sessions = get_recent_sessions(limit=100)

    if not sessions:
        return {
            "total_sessions": 0,
            "total_queries": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "most_used_models": {},
        }

    return {
        "total_sessions": len(sessions),
        "total_queries": sum(s.debates for s in sessions),
        "total_tokens": sum(s.total_tokens for s in sessions),
        "total_cost": sum(s.total_cost for s in sessions),
        "most_used_models": {},  # Now tracked in cloud
    }
