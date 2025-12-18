"""Synod Archives - Conversation context management with auto-compacting.

This module manages conversation history across interactive sessions,
automatically summarizing old exchanges when approaching token limits.
"""

from typing import List, Dict
from rich.console import Console


class CouncilArchives:
    """
    Manage conversation context across the session.
    Auto-compacts when approaching token limits (like Claude Code).

    Uses the "Synod Archives" metaphor - historical records of synod proceedings.
    """

    def __init__(self, max_tokens: int = 100000):
        """
        Initialize Synod Archives.

        Args:
            max_tokens: Maximum context tokens before auto-compact (default: 100k)
        """
        self.max_tokens = max_tokens
        self.exchanges: List[Dict] = []  # [{query, synthesis, tokens, is_summary}]
        self.current_tokens = 0

    def add_exchange(self, query: str, synthesis: str) -> None:
        """
        Add a debate exchange to archives.
        Auto-compacts if approaching token limit.

        Args:
            query: User's question
            synthesis: Pope's synthesized answer
        """
        tokens = self._estimate_tokens(query + synthesis)

        self.exchanges.append(
            {
                "query": query,
                "synthesis": synthesis,
                "tokens": tokens,
                "is_summary": False,
            }
        )
        self.current_tokens += tokens

        # Auto-compact at 80% usage
        if self.usage_percentage() > 80:
            self._compact_archives()

    def usage_percentage(self) -> float:
        """Calculate current context usage percentage."""
        if self.max_tokens == 0:
            return 0.0
        return (self.current_tokens / self.max_tokens) * 100

    def get_context_for_debate(self) -> str:
        """
        Format archives as context string for next debate.

        Returns recent exchanges in full, older ones as summaries.
        """
        if not self.exchanges:
            return ""

        context_parts = ["📜 **Synod Archives** (Previous Session Context):\n"]

        for i, ex in enumerate(self.exchanges):
            if ex.get("is_summary"):
                # Summarized old exchanges
                context_parts.append(ex["synthesis"])
            else:
                # Full recent exchange
                context_parts.append(f"\n**Exchange {i + 1}:**")
                context_parts.append(f"User Query: {ex['query']}")
                # Truncate synthesis to 500 chars for context
                synthesis_preview = (
                    ex["synthesis"][:500] + "..."
                    if len(ex["synthesis"]) > 500
                    else ex["synthesis"]
                )
                context_parts.append(f"Synod Decision: {synthesis_preview}\n")

        context_parts.append("\n---\n**Current Query:**\n")

        return "\n".join(context_parts)

    def _compact_archives(self) -> None:
        """
        Compact archives by summarizing old exchanges.
        Keeps last 2 exchanges in full, summarizes the rest.
        """
        if len(self.exchanges) <= 2:
            return  # Not enough to compact

        # Split into old (to summarize) and recent (keep full)
        old_exchanges = self.exchanges[:-2]
        recent_exchanges = self.exchanges[-2:]

        # Create summary of old exchanges
        summary_lines = ["📚 **Earlier Synod Sessions** (Summarized):\n"]
        for i, ex in enumerate(old_exchanges, 1):
            # Truncate for summary
            query_preview = (
                ex["query"][:80] + "..." if len(ex["query"]) > 80 else ex["query"]
            )
            synthesis_preview = (
                ex["synthesis"][:150] + "..."
                if len(ex["synthesis"]) > 150
                else ex["synthesis"]
            )

            summary_lines.append(f"  {i}. Q: {query_preview}")
            summary_lines.append(f"     A: {synthesis_preview}\n")

        summary_text = "\n".join(summary_lines)
        summary_tokens = self._estimate_tokens(summary_text)

        # Replace old exchanges with single summary entry
        self.exchanges = [
            {
                "query": "ARCHIVE_SUMMARY",
                "synthesis": summary_text,
                "tokens": summary_tokens,
                "is_summary": True,
            }
        ] + recent_exchanges

        # Recalculate total tokens
        self.current_tokens = sum(ex["tokens"] for ex in self.exchanges)

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count from text.

        Uses rough approximation: ~4 characters = 1 token
        """
        return len(text) // 4

    def display_status(self, console: Console) -> None:
        """
        Display archive status with color-coded usage indicator.

        Args:
            console: Rich console for output
        """
        usage = self.usage_percentage()
        remaining = 100 - usage

        # Color based on usage level
        if usage < 50:
            status_color = "green"
        elif usage < 80:
            status_color = "yellow"
        else:
            status_color = "red"

        console.print(
            f"[dim]📜 Synod Archives: {usage:.0f}% used • "
            f"[{status_color}]{remaining:.0f}% until synod refresh[/{status_color}][/dim]"
        )

    def compact(self) -> None:
        """Manually trigger archive compaction.

        This is useful when the user explicitly requests it via /compact.
        """
        self._compact_archives()

    def clear(self) -> None:
        """Clear all archives (fresh start)."""
        self.exchanges = []
        self.current_tokens = 0

    def get_exchange_count(self) -> int:
        """Get number of exchanges in archives."""
        return len([ex for ex in self.exchanges if not ex.get("is_summary")])
