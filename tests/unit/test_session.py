"""Unit tests for the session module."""

import json
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from synod.core.session import (
    SynodSession,
    ensure_sessions_dir,
    get_current_session,
    reset_session,
    end_session,
    get_all_sessions,
    get_recent_sessions,
    get_session_stats,
)


# ============================================================================
# SYNOD SESSION DATACLASS
# ============================================================================

class TestSynodSession:
    """Test SynodSession dataclass."""

    def test_default_session_creation(self):
        """Test creating session with defaults."""
        session = SynodSession()

        assert session.session_id is not None
        assert len(session.session_id) == 36  # UUID format
        assert session.start_time > 0
        assert session.debates == 0
        assert session.files_modified == 0
        assert session.total_tokens == 0
        assert session.total_cost == 0.0
        assert session.is_managed_mode is False
        assert session.total_debate_duration_ms == 0

    def test_session_with_custom_values(self):
        """Test creating session with custom values."""
        session = SynodSession(
            session_id="test-id",
            start_time=1000.0,
            debates=5,
            files_modified=10,
            total_tokens=5000,
            total_cost=0.05,
            is_managed_mode=True,
            total_debate_duration_ms=30000,
        )

        assert session.session_id == "test-id"
        assert session.start_time == 1000.0
        assert session.debates == 5
        assert session.files_modified == 10
        assert session.total_tokens == 5000
        assert session.total_cost == 0.05
        assert session.is_managed_mode is True
        assert session.total_debate_duration_ms == 30000

    def test_record_debate(self):
        """Test recording a debate."""
        session = SynodSession()

        session.record_debate(duration_ms=5000)
        assert session.debates == 1
        assert session.total_debate_duration_ms == 5000

        session.record_debate(duration_ms=3000)
        assert session.debates == 2
        assert session.total_debate_duration_ms == 8000

    def test_record_debate_no_duration(self):
        """Test recording debate without duration."""
        session = SynodSession()

        session.record_debate()
        assert session.debates == 1
        assert session.total_debate_duration_ms == 0

    def test_record_file_modification(self):
        """Test recording file modifications."""
        session = SynodSession()

        session.record_file_modification()
        assert session.files_modified == 1

        session.record_file_modification(count=5)
        assert session.files_modified == 6

    def test_get_duration(self):
        """Test getting session duration."""
        start_time = time.time() - 100  # 100 seconds ago
        session = SynodSession(start_time=start_time)

        duration = session.get_duration()
        assert 99 <= duration <= 101  # Allow small margin for execution time

    def test_get_summary(self):
        """Test getting session summary."""
        session = SynodSession()
        session.debates = 3
        session.files_modified = 5
        session.total_tokens = 10000
        session.total_cost = 0.10
        session.is_managed_mode = True
        session.total_debate_duration_ms = 15000

        summary = session.get_summary()

        assert "duration" in summary
        assert summary["debates"] == 3
        assert summary["files_modified"] == 5
        assert summary["total_tokens"] == 10000
        assert summary["total_cost"] == 0.10
        assert summary["is_managed_mode"] is True
        assert summary["total_debate_duration_ms"] == 15000

    def test_to_dict(self):
        """Test serializing session to dictionary."""
        session = SynodSession(session_id="test-123")
        session.debates = 2
        session.files_modified = 3

        data = session.to_dict()

        assert data["session_id"] == "test-123"
        assert data["debates"] == 2
        assert data["files_modified"] == 3
        assert "start_time" in data
        assert "duration" in data

    def test_save_and_load(self, temp_dir):
        """Test saving and loading a session."""
        # Patch SESSIONS_DIR to use temp_dir
        with patch('synod.core.session.SESSIONS_DIR', temp_dir):
            session = SynodSession()
            session.debates = 5
            session.files_modified = 10
            session.total_tokens = 5000

            # Save
            filepath = session.save()
            assert filepath.exists()

            # Load
            loaded = SynodSession.load(filepath)
            assert loaded.session_id == session.session_id
            assert loaded.debates == 5
            assert loaded.files_modified == 10
            assert loaded.total_tokens == 5000


# ============================================================================
# GLOBAL SESSION FUNCTIONS
# ============================================================================

class TestGlobalSession:
    """Test global session management functions."""

    def test_get_current_session_creates_new(self):
        """Test get_current_session creates session if none exists."""
        import synod.core.session as session_module
        session_module._current_session = None

        session = get_current_session()

        assert session is not None
        assert isinstance(session, SynodSession)

    def test_get_current_session_returns_same(self):
        """Test get_current_session returns same instance."""
        import synod.core.session as session_module
        session_module._current_session = None

        session1 = get_current_session()
        session2 = get_current_session()

        assert session1 is session2

    def test_reset_session(self):
        """Test reset_session creates new session."""
        import synod.core.session as session_module
        session_module._current_session = None

        session1 = get_current_session()
        session1.debates = 10

        session2 = reset_session()

        assert session2 is not session1
        assert session2.debates == 0

    def test_end_session(self):
        """Test end_session returns summary and resets."""
        import synod.core.session as session_module
        session_module._current_session = None

        session = get_current_session()
        session.debates = 5
        session.files_modified = 3

        summary = end_session()

        assert summary["debates"] == 5
        assert summary["files_modified"] == 3

        # Session should be reset
        new_session = get_current_session()
        assert new_session.debates == 0


# ============================================================================
# SESSION HISTORY
# ============================================================================

class TestSessionHistory:
    """Test session history functions."""

    def test_get_all_sessions_empty(self, temp_dir):
        """Test get_all_sessions returns empty when no sessions."""
        with patch('synod.core.session.SESSIONS_DIR', temp_dir / "nonexistent"):
            sessions = get_all_sessions()
            assert sessions == []

    def test_get_all_sessions_with_files(self, temp_dir):
        """Test get_all_sessions finds session files."""
        # Create some session files
        sessions_dir = temp_dir
        date_dir = sessions_dir / "2024-01-01"
        date_dir.mkdir(parents=True)

        (date_dir / "session1.json").write_text('{}')
        (date_dir / "session2.json").write_text('{}')

        with patch('synod.core.session.SESSIONS_DIR', sessions_dir):
            sessions = get_all_sessions()
            assert len(sessions) == 2

    def test_get_recent_sessions(self, temp_dir):
        """Test get_recent_sessions loads sessions."""
        # Create session files with valid data
        sessions_dir = temp_dir
        date_dir = sessions_dir / "2024-01-01"
        date_dir.mkdir(parents=True)

        session_data = {
            "session_id": "test-id",
            "start_time": time.time(),
            "debates": 5,
            "files_modified": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }
        (date_dir / "session1.json").write_text(json.dumps(session_data))

        with patch('synod.core.session.SESSIONS_DIR', sessions_dir):
            sessions = get_recent_sessions(limit=10)
            assert len(sessions) == 1
            assert sessions[0].debates == 5

    def test_get_recent_sessions_handles_invalid(self, temp_dir):
        """Test get_recent_sessions skips invalid files."""
        sessions_dir = temp_dir
        date_dir = sessions_dir / "2024-01-01"
        date_dir.mkdir(parents=True)

        # Invalid JSON
        (date_dir / "invalid.json").write_text('not json')

        with patch('synod.core.session.SESSIONS_DIR', sessions_dir):
            sessions = get_recent_sessions(limit=10)
            assert sessions == []

    def test_get_session_stats_empty(self, temp_dir):
        """Test get_session_stats with no sessions."""
        with patch('synod.core.session.SESSIONS_DIR', temp_dir / "nonexistent"):
            stats = get_session_stats()

            assert stats["total_sessions"] == 0
            assert stats["total_queries"] == 0
            assert stats["total_tokens"] == 0
            assert stats["total_cost"] == 0.0

    def test_get_session_stats_with_sessions(self, temp_dir):
        """Test get_session_stats aggregates data."""
        sessions_dir = temp_dir
        date_dir = sessions_dir / "2024-01-01"
        date_dir.mkdir(parents=True)

        # Create multiple session files
        for i in range(3):
            session_data = {
                "session_id": f"test-{i}",
                "start_time": time.time(),
                "debates": 2,
                "total_tokens": 1000,
                "total_cost": 0.10,
            }
            (date_dir / f"session{i}.json").write_text(json.dumps(session_data))

        with patch('synod.core.session.SESSIONS_DIR', sessions_dir):
            stats = get_session_stats()

            assert stats["total_sessions"] == 3
            assert stats["total_queries"] == 6  # 2 debates * 3 sessions
            assert stats["total_tokens"] == 3000  # 1000 * 3
            assert abs(stats["total_cost"] - 0.30) < 0.001  # 0.10 * 3 (float precision)


# ============================================================================
# ENSURE SESSIONS DIR
# ============================================================================

class TestEnsureSessionsDir:
    """Test ensure_sessions_dir function."""

    def test_creates_directory(self, temp_dir):
        """Test ensure_sessions_dir creates directory."""
        sessions_dir = temp_dir / "new_sessions"

        with patch('synod.core.session.SESSIONS_DIR', sessions_dir):
            result = ensure_sessions_dir()

            assert sessions_dir.exists()
            assert result == sessions_dir

    def test_returns_existing_directory(self, temp_dir):
        """Test ensure_sessions_dir with existing directory."""
        sessions_dir = temp_dir / "existing"
        sessions_dir.mkdir()

        with patch('synod.core.session.SESSIONS_DIR', sessions_dir):
            result = ensure_sessions_dir()

            assert sessions_dir.exists()
            assert result == sessions_dir
