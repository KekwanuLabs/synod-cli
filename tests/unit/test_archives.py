"""Unit tests for the archives module."""

import pytest
from io import StringIO
from rich.console import Console

from synod.core.archives import CouncilArchives


# ============================================================================
# INITIALIZATION
# ============================================================================

class TestCouncilArchivesInit:
    """Test CouncilArchives initialization."""

    def test_default_initialization(self):
        """Test default initialization values."""
        archives = CouncilArchives()

        assert archives.max_tokens == 100000
        assert archives.exchanges == []
        assert archives.current_tokens == 0

    def test_custom_max_tokens(self):
        """Test custom max_tokens initialization."""
        archives = CouncilArchives(max_tokens=50000)

        assert archives.max_tokens == 50000


# ============================================================================
# ADD EXCHANGE
# ============================================================================

class TestAddExchange:
    """Test add_exchange method."""

    def test_add_single_exchange(self):
        """Test adding a single exchange."""
        archives = CouncilArchives()
        archives.add_exchange("What is Python?", "Python is a programming language.")

        assert len(archives.exchanges) == 1
        assert archives.exchanges[0]['query'] == "What is Python?"
        assert archives.exchanges[0]['synthesis'] == "Python is a programming language."
        assert archives.exchanges[0]['is_summary'] is False
        assert archives.current_tokens > 0

    def test_add_multiple_exchanges(self):
        """Test adding multiple exchanges."""
        archives = CouncilArchives()
        archives.add_exchange("Q1", "A1")
        archives.add_exchange("Q2", "A2")
        archives.add_exchange("Q3", "A3")

        assert len(archives.exchanges) == 3
        assert archives.exchanges[0]['query'] == "Q1"
        assert archives.exchanges[2]['query'] == "Q3"

    def test_tokens_accumulate(self):
        """Test tokens accumulate across exchanges."""
        archives = CouncilArchives()

        archives.add_exchange("Short query", "Short answer")
        tokens1 = archives.current_tokens

        archives.add_exchange("Another query", "Another answer")
        tokens2 = archives.current_tokens

        assert tokens2 > tokens1


# ============================================================================
# USAGE PERCENTAGE
# ============================================================================

class TestUsagePercentage:
    """Test usage_percentage method."""

    def test_empty_archives(self):
        """Test usage percentage with empty archives."""
        archives = CouncilArchives()

        assert archives.usage_percentage() == 0.0

    def test_usage_increases(self):
        """Test usage percentage increases with exchanges."""
        archives = CouncilArchives(max_tokens=1000)
        archives.add_exchange("Test query", "Test response")

        assert archives.usage_percentage() > 0.0

    def test_zero_max_tokens(self):
        """Test handling of zero max_tokens."""
        archives = CouncilArchives(max_tokens=0)

        assert archives.usage_percentage() == 0.0


# ============================================================================
# GET CONTEXT FOR DEBATE
# ============================================================================

class TestGetContextForDebate:
    """Test get_context_for_debate method."""

    def test_empty_archives(self):
        """Test context from empty archives."""
        archives = CouncilArchives()

        assert archives.get_context_for_debate() == ""

    def test_context_includes_header(self):
        """Test context includes Synod Archives header."""
        archives = CouncilArchives()
        archives.add_exchange("Test", "Response")

        context = archives.get_context_for_debate()

        assert "Synod Archives" in context

    def test_context_includes_query_and_synthesis(self):
        """Test context includes query and synthesis."""
        archives = CouncilArchives()
        archives.add_exchange("What is the answer?", "The answer is 42.")

        context = archives.get_context_for_debate()

        assert "What is the answer?" in context
        assert "42" in context

    def test_context_truncates_long_synthesis(self):
        """Test long synthesis is truncated."""
        archives = CouncilArchives()
        long_synthesis = "A" * 1000  # Very long
        archives.add_exchange("Query", long_synthesis)

        context = archives.get_context_for_debate()

        assert "..." in context
        assert len(context) < len(long_synthesis) + 500

    def test_context_ends_with_current_query_marker(self):
        """Test context ends with current query marker."""
        archives = CouncilArchives()
        archives.add_exchange("Test", "Response")

        context = archives.get_context_for_debate()

        assert "**Current Query:**" in context


# ============================================================================
# COMPACT ARCHIVES
# ============================================================================

class TestCompactArchives:
    """Test archive compaction."""

    def test_no_compact_with_few_exchanges(self):
        """Test no compaction with 2 or fewer exchanges."""
        archives = CouncilArchives()
        archives.add_exchange("Q1", "A1")
        archives.add_exchange("Q2", "A2")

        # Manually trigger compaction
        archives._compact_archives()

        # Should still have 2 exchanges (no compaction)
        assert len(archives.exchanges) == 2

    def test_compact_with_many_exchanges(self):
        """Test compaction with many exchanges."""
        archives = CouncilArchives()
        for i in range(5):
            archives.add_exchange(f"Query {i}", f"Answer {i}")

        # Manually trigger compaction
        archives._compact_archives()

        # Should have 3: 1 summary + 2 recent
        assert len(archives.exchanges) == 3
        assert archives.exchanges[0]['is_summary'] is True

    def test_auto_compact_at_80_percent(self):
        """Test auto-compaction at 80% usage."""
        # Use small max_tokens to trigger compaction
        archives = CouncilArchives(max_tokens=100)

        # Add many exchanges to trigger 80% threshold
        for i in range(10):
            archives.add_exchange(f"Query {i}", f"A" * 50)

        # Should have compacted
        has_summary = any(ex.get('is_summary') for ex in archives.exchanges)
        assert has_summary or archives.usage_percentage() <= 100

    def test_compact_creates_summary(self):
        """Test compaction creates summary entry."""
        archives = CouncilArchives()
        for i in range(5):
            archives.add_exchange(f"Query {i}", f"Answer {i}")

        archives._compact_archives()

        summary_entries = [ex for ex in archives.exchanges if ex.get('is_summary')]
        assert len(summary_entries) == 1
        assert "Earlier Synod Sessions" in summary_entries[0]['synthesis']


# ============================================================================
# ESTIMATE TOKENS
# ============================================================================

class TestEstimateTokens:
    """Test _estimate_tokens method."""

    def test_estimate_short_text(self):
        """Test token estimation for short text."""
        archives = CouncilArchives()
        tokens = archives._estimate_tokens("Hello")  # 5 chars

        # ~4 chars per token, so 5/4 = 1
        assert tokens == 1

    def test_estimate_longer_text(self):
        """Test token estimation for longer text."""
        archives = CouncilArchives()
        text = "A" * 100  # 100 chars
        tokens = archives._estimate_tokens(text)

        assert tokens == 25  # 100 / 4

    def test_estimate_empty_text(self):
        """Test token estimation for empty text."""
        archives = CouncilArchives()
        tokens = archives._estimate_tokens("")

        assert tokens == 0


# ============================================================================
# DISPLAY STATUS
# ============================================================================

class TestDisplayStatus:
    """Test display_status method."""

    def test_display_low_usage_green(self):
        """Test low usage displays green."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        archives = CouncilArchives(max_tokens=10000)
        archives.add_exchange("Short", "Short")  # Low usage

        archives.display_status(console)

        output_text = output.getvalue()
        assert "Synod Archives" in output_text

    def test_display_shows_percentage(self):
        """Test display shows usage percentage."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        archives = CouncilArchives()
        archives.display_status(console)

        output_text = output.getvalue()
        assert "%" in output_text


# ============================================================================
# MANUAL OPERATIONS
# ============================================================================

class TestManualOperations:
    """Test manual operations on archives."""

    def test_compact_method(self):
        """Test manual compact method."""
        archives = CouncilArchives()
        for i in range(5):
            archives.add_exchange(f"Q{i}", f"A{i}")

        initial_count = len(archives.exchanges)
        archives.compact()

        # Should have fewer exchanges after compaction
        assert len(archives.exchanges) < initial_count

    def test_clear_method(self):
        """Test clear method."""
        archives = CouncilArchives()
        archives.add_exchange("Q1", "A1")
        archives.add_exchange("Q2", "A2")

        archives.clear()

        assert archives.exchanges == []
        assert archives.current_tokens == 0

    def test_get_exchange_count(self):
        """Test get_exchange_count method."""
        archives = CouncilArchives()
        archives.add_exchange("Q1", "A1")
        archives.add_exchange("Q2", "A2")
        archives.add_exchange("Q3", "A3")

        assert archives.get_exchange_count() == 3

    def test_get_exchange_count_excludes_summaries(self):
        """Test get_exchange_count excludes summary entries."""
        archives = CouncilArchives()
        for i in range(5):
            archives.add_exchange(f"Q{i}", f"A{i}")

        # Compact to create summary
        archives._compact_archives()

        # Should only count non-summary exchanges
        count = archives.get_exchange_count()
        assert count == 2  # Only the 2 recent, not the summary
