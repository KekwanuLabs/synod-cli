import time
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .model_registry import ModelProvider  # ModelProvider is defined in model_registry
from .model_registry import get_model_key # Added get_model_key import


# ============================================================================
# SESSION STORAGE
# ============================================================================

# Sessions directory
SESSIONS_DIR = Path.home() / ".synod-cli" / "sessions"

def ensure_sessions_dir() -> Path:
    """Ensure sessions directory exists.

    Returns:
        Path to sessions directory
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


# ============================================================================
# MODEL PRICING (per 1M tokens, by (model_id, provider) tuple)
# ============================================================================
MODEL_PRICING: Dict[Tuple[str, ModelProvider], Dict[str, float]] = {
    # Anthropic models (prices per 1M tokens)
    ("anthropic/claude-opus-4.5", ModelProvider.ANTHROPIC): {"input": 15.00, "output": 75.00},
    ("anthropic/claude-opus-4.5", ModelProvider.OPENROUTER): {"input": 15.00, "output": 75.00}, # OpenRouter often matches direct
    ("anthropic/claude-sonnet-4.5", ModelProvider.ANTHROPIC): {"input": 3.00, "output": 15.00},
    ("anthropic/claude-sonnet-4.5", ModelProvider.OPENROUTER): {"input": 3.00, "output": 15.00},
    ("anthropic/claude-haiku-4.5", ModelProvider.ANTHROPIC): {"input": 0.25, "output": 1.25},
    ("anthropic/claude-haiku-4.5", ModelProvider.OPENROUTER): {"input": 0.25, "output": 1.25},

    # OpenAI models (prices per 1M tokens)
    ("openai/gpt-5.1-chat", ModelProvider.OPENAI): {"input": 2.50, "output": 10.00}, # Speculative/Placeholder
    ("openai/gpt-5.1-chat", ModelProvider.AZURE_OPENAI): {"input": 2.50, "output": 10.00}, # Speculative/Placeholder
    ("openai/gpt-5.1-chat", ModelProvider.OPENROUTER): {"input": 2.50, "output": 10.00}, # Speculative/Placeholder
    ("openai/gpt-5.1", ModelProvider.OPENAI): {"input": 2.50, "output": 10.00}, # Speculative/Placeholder
    ("openai/gpt-5.1", ModelProvider.AZURE_OPENAI): {"input": 2.50, "output": 10.00}, # Speculative/Placeholder
    ("openai/gpt-5.1", ModelProvider.OPENROUTER): {"input": 2.50, "output": 10.00}, # Speculative/Placeholder
    ("openai/gpt-4o", ModelProvider.OPENAI): {"input": 5.00, "output": 15.00},
    ("openai/gpt-4o", ModelProvider.AZURE_OPENAI): {"input": 5.00, "output": 15.00},
    ("openai/gpt-4o", ModelProvider.OPENROUTER): {"input": 2.50, "output": 10.00}, # OpenRouter is cheaper for 4o
    ("openai/gpt-4-turbo", ModelProvider.OPENAI): {"input": 10.00, "output": 30.00},
    ("openai/gpt-4-turbo", ModelProvider.AZURE_OPENAI): {"input": 10.00, "output": 30.00},
    ("openai/gpt-4-turbo", ModelProvider.OPENROUTER): {"input": 5.00, "output": 15.00},

    # Google models (prices per 1M tokens)
    ("google/gemini-3-pro-preview", ModelProvider.OPENROUTER): {"input": 1.25, "output": 5.00},
    ("google/gemini-2.5-flash", ModelProvider.OPENROUTER): {"input": 0.075, "output": 0.30},

    # xAI Grok (prices per 1M tokens)
    ("x-ai/grok-4.1-fast:free", ModelProvider.OPENROUTER): {"input": 0.00, "output": 0.00}, # Free tier

    # DeepSeek models (prices per 1M tokens)
    ("deepseek/deepseek-v3.1", ModelProvider.DEEPSEEK): {"input": 0.14, "output": 0.28},
    ("deepseek/deepseek-v3.1", ModelProvider.OPENROUTER): {"input": 0.14, "output": 0.28},

    # Zhipu AI GLM (prices per 1M tokens)
    ("z-ai/glm-4.6", ModelProvider.OPENROUTER): {"input": 0.15, "output": 0.20},
}

# Context window limits (in tokens)
MODEL_CONTEXT_LIMITS = {
    "anthropic/claude-opus-4.5": 200000,
    "anthropic/claude-sonnet-4.5": 200000,
    "anthropic/claude-haiku-4.5": 200000,
    "openai/gpt-4o": 128000,
    "openai/gpt-4-turbo": 128000,
    "deepseek/deepseek-v3.1": 64000,
    "google/gemini-3-pro-preview": 1000000, # Large context for Gemini
    "google/gemini-2.5-flash": 1000000,
    "x-ai/grok-4.1-fast:free": 131072, # Assuming large context
    "z-ai/glm-4.6": 128000,
}

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class BishopUsage:
    """Track usage for a single bishop."""

    model_id: str
    provider: ModelProvider # Add provider to usage tracking
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    calls: int = 0

    def add_usage(
        self, input_tokens: int, output_tokens: int, cost: Optional[float] = None
    ) -> None:
        """Add usage from an API call.

        Args:
            input_tokens: Prompt tokens
            output_tokens: Completion tokens
            cost: Actual cost (if provided by API), otherwise calculated
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens = self.input_tokens + self.output_tokens
        self.calls += 1

        # Calculate cost if not provided
        if cost is not None:
            self.cost += cost
        else:
            self.cost += self._calculate_cost(input_tokens, output_tokens)

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for a model call.

        Args:
            input_tokens: Prompt tokens
            output_tokens: Completion tokens

        Returns:
            Cost in USD
        """
        pricing = MODEL_PRICING.get((self.model_id, self.provider), None)

        if pricing is None:
            # Fallback if specific (model, provider) pricing not found
            # Try to find a default price for the model without provider
            # This logic might need refinement if a model has drastically different prices across providers
            # and no specific (model, provider) tuple is found.
            for (model_key, _), prices in MODEL_PRICING.items():
                if model_key == self.model_id:
                    pricing = prices
                    break
            if pricing is None: # Still no pricing found
                # print(f"Warning: Pricing not found for model {self.model_id} via provider {self.provider.value}. Cost estimated as $0.0.")
                return 0.0 # Default to 0 if no price found

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def get_percentage(self, total_tokens: int) -> float:
        """Calculate percentage of total tokens.

        Args:
            total_tokens: Total tokens across all bishops

        Returns:
            Percentage (0-100)
        """
        if total_tokens == 0:
            return 0.0
        return (self.total_tokens / total_tokens) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "model_id": self.model_id,
            "tokens": self.total_tokens,
            "cost": self.cost,
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

@dataclass
class SynodSession:
    """Track a complete Synod session.

    Attributes:
        session_id: Unique session identifier (UUID)
        start_time: Session start timestamp
        debates: Number of debates completed
        files_modified: Number of files changed
        bishop_usage: Per-bishop usage tracking
        total_tokens: Total tokens across all bishops
        total_cost: Total cost in USD
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float = field(default_factory=time.time)
    debates: int = 0
    files_modified: int = 0
    bishop_usage: Dict[str, BishopUsage] = field(default_factory=dict)
    total_tokens: int = 0
    total_cost: float = 0.0

    def record_api_call(
        self,
        model_id: str,
        provider: ModelProvider, # New argument
        input_tokens: int,
        output_tokens: int,
        cost: Optional[float] = None,
    ) -> None:
        """Record an API call to a bishop.

        Args:
            model_id: Model identifier
            provider: The ModelProvider that served the request
            input_tokens: Prompt tokens
            output_tokens: Completion tokens
            cost: Actual cost (if provided)
        """
        # Ensure the model_id is canonical for consistent tracking
        canonical_model_id = get_model_key(model_id) # Canonicalize here

        # Use a combined key for uniqueness (model_id + provider)
        usage_key = f"{canonical_model_id}::{provider.value}"
        
        if usage_key not in self.bishop_usage:
            self.bishop_usage[usage_key] = BishopUsage(model_id=canonical_model_id, provider=provider) # Pass provider here

        # Add usage
        self.bishop_usage[usage_key].add_usage(input_tokens, output_tokens, cost)

        # Update totals
        self._update_totals()

    def record_debate(self) -> None:
        """Increment debate counter."""
        self.debates += 1

    def record_file_modification(self, count: int = 1) -> None:
        """Record file modifications.

        Args:
            count: Number of files modified
        """
        self.files_modified += count

    def _update_totals(self) -> None:
        """Recalculate total tokens and cost."""
        self.total_tokens = sum(
            bishop.total_tokens for bishop in self.bishop_usage.values()
        )
        self.total_cost = sum(bishop.cost for bishop in self.bishop_usage.values())

    def get_duration(self) -> float:
        """Get session duration in seconds.

        Returns:
            Duration in seconds
        """
        return time.time() - self.start_time

    def get_context_usage(self, max_context: int = 200000) -> float:
        """Calculate context window usage percentage.

        Args:
            max_context: Maximum context window size

        Returns:
            Percentage used (0-100)
        """
        if max_context == 0:
            return 0.0
        return (self.total_tokens / max_context) * 100

    def get_most_active_bishop(self) -> Optional[str]:
        """Get the bishop with most tokens used.

        Returns:
            Model ID of most active bishop, or None if no usage
        """
        if not self.bishop_usage:
            return None

        most_active = max(
            self.bishop_usage.items(), key=lambda x: x[1].total_tokens
        )
        return most_active[0]

    def get_summary(self) -> Dict[str, Any]:
        """Get session summary for display.

        Returns:
            Dictionary with session metrics
        """
        summary = {
            "duration": self.get_duration(),
            "debates": self.debates,
            "files_modified": self.files_modified,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "bishop_usage": {},
        }

        # Add per-bishop data with percentages, aggregating across providers
        for usage_key, usage in self.bishop_usage.items():
            model_id = usage.model_id # Get the base model_id
            if model_id not in summary["bishop_usage"]:
                summary["bishop_usage"][model_id] = {
                    "tokens": 0, "cost": 0.0, "calls": 0, "percentage": 0.0
                }
            
            summary["bishop_usage"][model_id]["tokens"] += usage.total_tokens
            summary["bishop_usage"][model_id]["cost"] += usage.cost
            summary["bishop_usage"][model_id]["calls"] += usage.calls

        # Recalculate percentages after aggregation
        for model_id in summary["bishop_usage"]:
            summary["bishop_usage"][model_id]["percentage"] = (
                (summary["bishop_usage"][model_id]["tokens"] / self.total_tokens) * 100
                if self.total_tokens > 0 else 0.0
            )

        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "duration": self.get_duration(),
            "debates": self.debates,
            "files_modified": self.files_modified,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "bishops": {
                usage_key: usage.to_dict() # Use usage_key here
                for usage_key, usage in self.bishop_usage.items()
            },
        }

    def save(self) -> Path:
        """Save session to disk.

        Returns:
            Path to saved session file
        """
        ensure_sessions_dir()

        # Organize by date for easier browsing
        date_str = datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d")
        date_dir = SESSIONS_DIR / date_str
        date_dir.mkdir(exist_ok=True)

        # Filename: timestamp_sessionid.json
        timestamp = datetime.fromtimestamp(self.start_time).strftime("%H-%M-%S")
        filename = f"{timestamp}_{self.session_id[:8]}.json"
        filepath = date_dir / filename

        # Save to JSON
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        return filepath

    @classmethod
    def load(cls, filepath: Path) -> 'SynodSession':
        """Load session from disk.

        Args:
            filepath: Path to session JSON file

        Returns:
            SynodSession instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)

        # Recreate session
        session = cls(
            session_id=data["session_id"],
            start_time=data["start_time"],
            debates=data["debates"],
            files_modified=data["files_modified"],
        )

        # Restore bishop usage
        # Iterate over usage_key (model_id::provider_value)
        for usage_key, usage_data in data.get("bishops", {}).items():
            model_id_from_key, provider_value = usage_key.split("::")
            session.bishop_usage[usage_key] = BishopUsage(
                model_id=usage_data["model_id"], # Should match model_id_from_key
                provider=ModelProvider(provider_value),
                input_tokens=usage_data["input_tokens"],
                output_tokens=usage_data["output_tokens"],
                total_tokens=usage_data["tokens"],
                cost=usage_data["cost"],
                calls=usage_data["calls"],
            )

        # Update totals
        session._update_totals()

        return session

# ============================================================================
# GLOBAL SESSION INSTANCE
# ============================================================================

# Global session instance - initialized when Synod starts
_current_session: Optional[SynodSession] = None

def get_current_session() -> SynodSession:
    """Get or create the current session.

    Returns:
        Current SynodSession instance
    """
    global _current_session
    if _current_session is None:
        _current_session = SynodSession()
    return _current_session

def reset_session() -> SynodSession:
    """Reset the current session.

    Returns:
        New SynodSession instance
    """
    global _current_session
    _current_session = SynodSession()
    return _current_session

def end_session() -> Dict[str, Any]:
    """End the current session and return summary.

    Returns:
        Session summary dictionary
    """
    session = get_current_session()
    summary = session.get_summary()
    reset_session()
    return summary

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_openrouter_usage(response_data: Dict[str, Any]) -> Dict[str, int]:
    """Parse usage data from OpenRouter API response.

    Args:
        response_data: Full API response from OpenRouter

    Returns:
        Dictionary with 'input_tokens' and 'output_tokens'
    """
    usage = response_data.get("usage", {})
    return {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }

def estimate_token_count(text: str) -> int:
    """Rough estimation of token count from text.

    Args:
        text: Input text

    Returns:
        Estimated token count (rough: ~4 chars = 1 token)
    """
    # Very rough approximation: average ~4 characters per token
    # This is a fallback when actual token count isn't available
    return len(text) // 4

def get_model_context_limit(model_id: str) -> int:
    """Get context window limit for a model.

    Args:
        model_id: Model identifier

    Returns:
        Context limit in tokens
    """
    return MODEL_CONTEXT_LIMITS.get(model_id, 128000)  # Default to 128k


def display_session_summary(session: SynodSession) -> None:
    """Display beautiful session summary on exit (inspired by Gemini).

    Args:
        session: The session to summarize
    """
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich.panel import Panel
    from rich.box import ROUNDED

    console = Console()

    # Use real session ID (truncated for display)
    session_id = session.session_id[:32]

    # Calculate metrics
    duration = session.get_duration()
    duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"

    # Success rate (debates / attempted queries)
    success_rate = 100.0 if session.debates > 0 else 0.0
    total_calls = sum(b.calls for b in session.bishop_usage.values())

    # Build summary text
    summary = Text()

    # Header
    summary.append("\n🏛️  Council Dismissed\n\n", style="bold cyan")

    # Interaction Summary
    summary.append("Interaction Summary\n", style="bold")
    summary.append(f"Session ID:           {session_id}\n", style="dim")
    summary.append(f"Queries:              {session.debates}\n", style="dim")
    success_icon = "✓" if success_rate == 100 else "⚠"
    summary.append(f"Success Rate:         {success_icon} {success_rate:.0f}%\n\n", style="dim")

    # Performance
    summary.append("Performance\n", style="bold")
    summary.append(f"Session Time:         {duration_str}\n", style="dim")
    summary.append(f"Total API Calls:      {total_calls}\n\n", style="dim")

    # Cost Summary
    summary.append("Cost Summary\n", style="bold")
    summary.append(f"Total Tokens:         {session.total_tokens:,}\n", style="dim")
    summary.append(f"Total Cost:           ${session.total_cost:.4f}\n\n", style="dim")

    # Model Usage Table
    if session.bishop_usage:
        summary.append("Model Usage\n\n", style="bold")

        # Create table
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Model", style="cyan")
        table.add_column("Reqs", justify="right", style="dim")
        table.add_column("Input Tokens", justify="right", style="dim")
        table.add_column("Output Tokens", justify="right", style="dim")
        table.add_column("Cost", justify="right", style="yellow")

        # Aggregate usage if multiple entries for same model_id (e.g., from different providers)
        aggregated_usage: Dict[str, Any] = {}
        for usage_key, usage in session.bishop_usage.items():
            model_id = usage.model_id
            if model_id not in aggregated_usage:
                aggregated_usage[model_id] = {
                    "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0
                }
            aggregated_usage[model_id]["calls"] += usage.calls
            aggregated_usage[model_id]["input_tokens"] += usage.input_tokens
            aggregated_usage[model_id]["output_tokens"] += usage.output_tokens
            aggregated_usage[model_id]["cost"] += usage.cost
        
        # Sort aggregated usage for display
        sorted_aggregated_usage = sorted(
            aggregated_usage.items(),
            key=lambda x: x[1]["input_tokens"] + x[1]["output_tokens"], # Sort by total tokens
            reverse=True
        )

        for model_id, usage_data in sorted_aggregated_usage:
            # Shorten model name
            model_name = model_id.split('/')[-1] if '/' in model_id else model_id
            if len(model_name) > 30:
                model_name = model_name[:27] + "..."

            table.add_row(
                model_name,
                str(usage_data["calls"]),
                f"{usage_data['input_tokens']:,}",
                f"{usage_data['output_tokens']:,}",
                f"${usage_data['cost']:.4f}"
            )

        # Print summary text
        console.print(Panel(summary, border_style="cyan", box=ROUNDED))
        console.print()

        # Print table
        console.print(table)
        console.print()
    else:
        # No usage
        console.print(Panel(summary, border_style="cyan", box=ROUNDED))
        console.print()


# ============================================================================
# SESSION HISTORY
# ============================================================================

def get_all_sessions() -> List[Path]:
    """Get all saved session files.

    Returns:
        List of session file paths, sorted by date (newest first)
    """
    if not SESSIONS_DIR.exists():
        return []

    # Get all JSON files recursively
    sessions = list(SESSIONS_DIR.rglob("*.json"))

    # Sort by modification time (newest first)
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return sessions


def get_recent_sessions(limit: int = 10) -> List[SynodSession]:
    """Get recent sessions.

    Args:
        limit: Maximum number of sessions to return

    Returns:
        List of SynodSession instances, sorted by date (newest first)
    """
    session_files = get_all_sessions()[:limit]

    sessions = []
    for filepath in session_files:
        try:
            sessions.append(SynodSession.load(filepath))
        except Exception:
            # Skip corrupted session files
            continue

    return sessions


def get_session_stats() -> Dict[str, Any]:
    """Get aggregate statistics across all sessions.

    Returns:
        Dictionary with aggregate stats
    """
    sessions = get_recent_sessions(limit=100)  # Last 100 sessions

    if not sessions:
        return {
            "total_sessions": 0,
            "total_queries": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "most_used_models": {},
        }

    total_queries = sum(s.debates for s in sessions)
    total_tokens = sum(s.total_tokens for s in sessions)
    total_cost = sum(s.total_cost for s in sessions)

    # Count model usage
    model_usage: Dict[str, int] = {}
    for session in sessions:
        for model_id, usage in session.bishop_usage.items():
            if model_id not in model_usage:
                model_usage[model_id] = 0
            model_usage[model_id] += usage.calls

    # Sort by usage
    most_used = dict(sorted(model_usage.items(), key=lambda x: x[1], reverse=True)[:5])

    return {
        "total_sessions": len(sessions),
        "total_queries": total_queries,
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "most_used_models": most_used,
    }


def cleanup_old_sessions(days: int = 30) -> int:
    """Delete sessions older than specified days.

    Args:
        days: Number of days to keep

    Returns:
        Number of sessions deleted
    """
    if not SESSIONS_DIR.exists():
        return 0

    cutoff_time = time.time() - (days * 24 * 60 * 60)
    deleted = 0

    for session_file in get_all_sessions():
        if session_file.stat().st_mtime < cutoff_time:
            session_file.unlink()
            deleted += 1

    # Remove empty date directories
    for date_dir in SESSIONS_DIR.iterdir():
        if date_dir.is_dir() and not list(date_dir.iterdir()):
            date_dir.rmdir()

    return deleted
