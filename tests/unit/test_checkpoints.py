"""Unit tests for the checkpoint/undo system."""

import json
import pytest
from pathlib import Path
from datetime import datetime

from synod.core.checkpoints import (
    Checkpoint,
    FileBackup,
    CheckpointManager,
    create_checkpoint,
    restore_latest,
    get_checkpoint_manager,
    reset_checkpoint_manager,
    handle_rewind_command,
)


# ============================================================================
# DATA CLASSES
# ============================================================================

class TestFileBackup:
    """Test FileBackup dataclass."""

    def test_backup_existing_file(self):
        """Test backup of existing file."""
        backup = FileBackup(
            path="src/main.py",
            original_content="print('hello')",
            existed=True,
        )
        assert backup.path == "src/main.py"
        assert backup.original_content == "print('hello')"
        assert backup.existed is True

    def test_backup_new_file(self):
        """Test backup of file that didn't exist."""
        backup = FileBackup(
            path="new_file.py",
            original_content=None,
            existed=False,
        )
        assert backup.existed is False
        assert backup.original_content is None


class TestCheckpoint:
    """Test Checkpoint dataclass."""

    def test_checkpoint_creation(self):
        """Test creating a checkpoint."""
        checkpoint = Checkpoint(
            id="123456_1",
            timestamp=1234567890.0,
            action="edit src/main.py",
            files=[FileBackup("src/main.py", "old content", True)],
            conversation_index=1,
        )
        assert checkpoint.id == "123456_1"
        assert checkpoint.action == "edit src/main.py"
        assert len(checkpoint.files) == 1

    def test_checkpoint_to_dict(self):
        """Test serializing checkpoint."""
        checkpoint = Checkpoint(
            id="test_1",
            timestamp=1000.0,
            action="create file",
            files=[FileBackup("test.py", None, False)],
        )
        data = checkpoint.to_dict()

        assert data["id"] == "test_1"
        assert data["timestamp"] == 1000.0
        assert len(data["files"]) == 1
        assert data["files"][0]["existed"] is False

    def test_checkpoint_from_dict(self):
        """Test deserializing checkpoint."""
        data = {
            "id": "cp_123",
            "timestamp": 2000.0,
            "action": "str_replace main.py",
            "files": [
                {"path": "main.py", "original_content": "old", "existed": True}
            ],
            "conversation_index": 5,
        }
        checkpoint = Checkpoint.from_dict(data)

        assert checkpoint.id == "cp_123"
        assert checkpoint.action == "str_replace main.py"
        assert checkpoint.files[0].original_content == "old"
        assert checkpoint.conversation_index == 5


# ============================================================================
# CHECKPOINT MANAGER
# ============================================================================

class TestCheckpointManager:
    """Test CheckpointManager class."""

    def test_manager_initialization(self, temp_project):
        """Test manager initialization."""
        manager = CheckpointManager(str(temp_project))
        assert manager.project_path == Path(temp_project).resolve()

    def test_create_checkpoint(self, temp_project, sample_python_file):
        """Test creating a checkpoint."""
        # Move sample file into project
        target = temp_project / "sample.py"
        target.write_text(sample_python_file.read_text())

        manager = CheckpointManager(str(temp_project))
        checkpoint = manager.create_checkpoint(
            action="edit sample.py",
            files_to_backup=["sample.py"],
        )

        assert checkpoint.id is not None
        assert checkpoint.action == "edit sample.py"
        assert len(checkpoint.files) == 1
        assert checkpoint.files[0].existed is True
        assert "def hello" in checkpoint.files[0].original_content

    def test_create_checkpoint_nonexistent_file(self, temp_project):
        """Test checkpoint for file that doesn't exist yet."""
        manager = CheckpointManager(str(temp_project))
        checkpoint = manager.create_checkpoint(
            action="create new.py",
            files_to_backup=["new.py"],
        )

        assert len(checkpoint.files) == 1
        assert checkpoint.files[0].existed is False
        assert checkpoint.files[0].original_content is None

    def test_get_checkpoints(self, temp_project):
        """Test retrieving checkpoints."""
        manager = CheckpointManager(str(temp_project))

        # Create a few checkpoints
        manager.create_checkpoint("action 1", ["file1.py"])
        manager.create_checkpoint("action 2", ["file2.py"])
        manager.create_checkpoint("action 3", ["file3.py"])

        checkpoints = manager.get_checkpoints(limit=10)

        assert len(checkpoints) == 3
        # Should be newest first
        assert checkpoints[0].action == "action 3"

    def test_restore_checkpoint(self, temp_project):
        """Test restoring a checkpoint."""
        # Create a file
        test_file = temp_project / "restore_test.py"
        test_file.write_text("original content")

        manager = CheckpointManager(str(temp_project))
        checkpoint = manager.create_checkpoint(
            action="edit restore_test.py",
            files_to_backup=["restore_test.py"],
        )

        # Modify the file
        test_file.write_text("modified content")
        assert test_file.read_text() == "modified content"

        # Restore
        result = manager.restore_checkpoint(checkpoint.id)

        assert result is True
        assert test_file.read_text() == "original content"

    def test_restore_removes_created_file(self, temp_project):
        """Test restoring removes files that were created after checkpoint."""
        manager = CheckpointManager(str(temp_project))

        # Checkpoint before file exists
        checkpoint = manager.create_checkpoint(
            action="create new_file.py",
            files_to_backup=["new_file.py"],
        )

        # Create the file
        new_file = temp_project / "new_file.py"
        new_file.write_text("new content")
        assert new_file.exists()

        # Restore should remove the file
        result = manager.restore_checkpoint(checkpoint.id)

        assert result is True
        assert not new_file.exists()

    def test_restore_nonexistent_checkpoint(self, temp_project, capsys):
        """Test restoring non-existent checkpoint."""
        manager = CheckpointManager(str(temp_project))
        result = manager.restore_checkpoint("nonexistent_123")

        assert result is False

    def test_cleanup_old_checkpoints(self, temp_project):
        """Test that old checkpoints are cleaned up."""
        manager = CheckpointManager(str(temp_project))

        # Create more than MAX_CHECKPOINTS
        for i in range(25):
            manager.create_checkpoint(f"action {i}", [f"file{i}.py"])

        # Should only keep last 20
        checkpoints = list((temp_project / ".synod" / "checkpoints").glob("*.json"))
        assert len(checkpoints) == 20

    def test_get_latest_checkpoint(self, temp_project):
        """Test getting the latest checkpoint."""
        manager = CheckpointManager(str(temp_project))

        manager.create_checkpoint("first", ["a.py"])
        manager.create_checkpoint("second", ["b.py"])
        manager.create_checkpoint("latest", ["c.py"])

        latest = manager.get_latest_checkpoint()

        assert latest is not None
        assert latest.action == "latest"


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_create_checkpoint_function(self, temp_project):
        """Test create_checkpoint convenience function."""
        reset_checkpoint_manager()

        # Initialize manager with project path
        import synod.core.checkpoints as cp_module
        cp_module._checkpoint_manager = CheckpointManager(str(temp_project))

        checkpoint = create_checkpoint("test action", ["test.py"])

        assert checkpoint.action == "test action"

    def test_restore_latest_no_checkpoints(self, temp_project, capsys):
        """Test restore_latest with no checkpoints."""
        reset_checkpoint_manager()

        import synod.core.checkpoints as cp_module
        cp_module._checkpoint_manager = CheckpointManager(str(temp_project))

        result = restore_latest()

        assert result is False

    def test_get_checkpoint_manager_singleton(self, temp_project):
        """Test checkpoint manager is a singleton."""
        reset_checkpoint_manager()

        manager1 = get_checkpoint_manager(str(temp_project))
        manager2 = get_checkpoint_manager()

        assert manager1 is manager2


# ============================================================================
# COMMAND HANDLER
# ============================================================================

class TestRewindCommand:
    """Test /rewind command handler."""

    @pytest.mark.asyncio
    async def test_rewind_no_checkpoints(self, temp_project, capsys):
        """Test /rewind with no checkpoints."""
        reset_checkpoint_manager()

        import synod.core.checkpoints as cp_module
        cp_module._checkpoint_manager = CheckpointManager(str(temp_project))

        await handle_rewind_command("")

        captured = capsys.readouterr()
        assert "No checkpoints available" in captured.out
