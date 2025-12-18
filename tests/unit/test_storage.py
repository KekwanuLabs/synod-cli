"""Unit tests for the storage module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from synod.core.storage import (
    ensure_data_dir,
    get_conversation_path,
    create_conversation,
    get_conversation,
    save_conversation,
    list_conversations,
    add_user_message,
    add_assistant_message,
    update_conversation_title,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

class TestHelperFunctions:
    """Test helper functions."""

    def test_ensure_data_dir_creates_directory(self, temp_dir):
        """Test ensure_data_dir creates the directory."""
        data_dir = temp_dir / "conversations"

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            ensure_data_dir()
            assert data_dir.exists()

    def test_ensure_data_dir_existing(self, temp_dir):
        """Test ensure_data_dir with existing directory."""
        data_dir = temp_dir / "conversations"
        data_dir.mkdir()

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            ensure_data_dir()  # Should not raise
            assert data_dir.exists()

    def test_get_conversation_path(self, temp_dir):
        """Test get_conversation_path returns correct path."""
        data_dir = temp_dir / "conversations"

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            path = get_conversation_path("test-id")
            assert path == str(data_dir / "test-id.json")


# ============================================================================
# CREATE CONVERSATION
# ============================================================================

class TestCreateConversation:
    """Test create_conversation function."""

    def test_create_conversation_basic(self, temp_dir):
        """Test creating a basic conversation."""
        data_dir = temp_dir / "conversations"

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            conversation = create_conversation("test-123")

            assert conversation["id"] == "test-123"
            assert conversation["title"] == "New Conversation"
            assert conversation["messages"] == []
            assert "created_at" in conversation

            # File should exist
            assert (data_dir / "test-123.json").exists()

    def test_create_conversation_file_content(self, temp_dir):
        """Test created conversation file has correct content."""
        data_dir = temp_dir / "conversations"

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            create_conversation("test-456")

            # Read and verify file content
            with open(data_dir / "test-456.json") as f:
                data = json.load(f)

            assert data["id"] == "test-456"
            assert data["title"] == "New Conversation"
            assert data["messages"] == []


# ============================================================================
# GET CONVERSATION
# ============================================================================

class TestGetConversation:
    """Test get_conversation function."""

    def test_get_existing_conversation(self, temp_dir):
        """Test getting an existing conversation."""
        data_dir = temp_dir / "conversations"
        data_dir.mkdir()

        # Create a conversation file
        conv_data = {
            "id": "existing-conv",
            "title": "Test Title",
            "messages": [{"role": "user", "content": "Hello"}],
            "created_at": "2024-01-01T00:00:00"
        }
        with open(data_dir / "existing-conv.json", "w") as f:
            json.dump(conv_data, f)

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            conversation = get_conversation("existing-conv")

            assert conversation is not None
            assert conversation["id"] == "existing-conv"
            assert conversation["title"] == "Test Title"
            assert len(conversation["messages"]) == 1

    def test_get_nonexistent_conversation(self, temp_dir):
        """Test getting a non-existent conversation."""
        data_dir = temp_dir / "conversations"
        data_dir.mkdir()

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            conversation = get_conversation("nonexistent")
            assert conversation is None


# ============================================================================
# SAVE CONVERSATION
# ============================================================================

class TestSaveConversation:
    """Test save_conversation function."""

    def test_save_conversation(self, temp_dir):
        """Test saving a conversation."""
        data_dir = temp_dir / "conversations"

        conversation = {
            "id": "save-test",
            "title": "Saved Title",
            "messages": [{"role": "user", "content": "Test"}],
            "created_at": "2024-01-01T00:00:00"
        }

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            save_conversation(conversation)

            # Verify file was saved
            assert (data_dir / "save-test.json").exists()

            with open(data_dir / "save-test.json") as f:
                saved = json.load(f)

            assert saved["title"] == "Saved Title"
            assert len(saved["messages"]) == 1


# ============================================================================
# LIST CONVERSATIONS
# ============================================================================

class TestListConversations:
    """Test list_conversations function."""

    def test_list_empty_directory(self, temp_dir):
        """Test listing conversations from empty directory."""
        data_dir = temp_dir / "conversations"

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            conversations = list_conversations()
            assert conversations == []

    def test_list_conversations_returns_metadata(self, temp_dir):
        """Test list_conversations returns metadata only."""
        data_dir = temp_dir / "conversations"
        data_dir.mkdir()

        # Create conversation files
        for i, time_suffix in enumerate(["01", "02", "03"]):
            conv_data = {
                "id": f"conv-{i}",
                "title": f"Conversation {i}",
                "messages": [{"role": "user", "content": "msg"} for _ in range(i + 1)],
                "created_at": f"2024-01-{time_suffix}T00:00:00"
            }
            with open(data_dir / f"conv-{i}.json", "w") as f:
                json.dump(conv_data, f)

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            conversations = list_conversations()

            assert len(conversations) == 3

            # Check sorted by creation time (newest first)
            assert conversations[0]["id"] == "conv-2"
            assert conversations[1]["id"] == "conv-1"
            assert conversations[2]["id"] == "conv-0"

            # Check metadata fields
            for conv in conversations:
                assert "id" in conv
                assert "title" in conv
                assert "created_at" in conv
                assert "message_count" in conv
                assert "messages" not in conv  # Full messages not included


# ============================================================================
# ADD USER MESSAGE
# ============================================================================

class TestAddUserMessage:
    """Test add_user_message function."""

    def test_add_user_message(self, temp_dir):
        """Test adding a user message."""
        data_dir = temp_dir / "conversations"
        data_dir.mkdir()

        # Create initial conversation
        conv_data = {
            "id": "msg-test",
            "title": "Test",
            "messages": [],
            "created_at": "2024-01-01T00:00:00"
        }
        with open(data_dir / "msg-test.json", "w") as f:
            json.dump(conv_data, f)

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            add_user_message("msg-test", "Hello, world!")

            # Verify message was added
            conversation = get_conversation("msg-test")
            assert len(conversation["messages"]) == 1
            assert conversation["messages"][0]["role"] == "user"
            assert conversation["messages"][0]["content"] == "Hello, world!"

    def test_add_user_message_nonexistent(self, temp_dir):
        """Test adding message to non-existent conversation."""
        data_dir = temp_dir / "conversations"
        data_dir.mkdir()

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            with pytest.raises(ValueError, match="not found"):
                add_user_message("nonexistent", "Hello")


# ============================================================================
# ADD ASSISTANT MESSAGE
# ============================================================================

class TestAddAssistantMessage:
    """Test add_assistant_message function."""

    def test_add_assistant_message(self, temp_dir):
        """Test adding an assistant message with all stages."""
        data_dir = temp_dir / "conversations"
        data_dir.mkdir()

        # Create initial conversation
        conv_data = {
            "id": "assist-test",
            "title": "Test",
            "messages": [],
            "created_at": "2024-01-01T00:00:00"
        }
        with open(data_dir / "assist-test.json", "w") as f:
            json.dump(conv_data, f)

        stage1 = [{"model": "claude", "response": "Stage 1 response"}]
        stage2 = [{"model": "claude", "ranking": 1}]
        stage3 = {"final": "Synthesized response"}

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            add_assistant_message("assist-test", stage1, stage2, stage3)

            conversation = get_conversation("assist-test")
            assert len(conversation["messages"]) == 1

            msg = conversation["messages"][0]
            assert msg["role"] == "assistant"
            assert msg["stage1"] == stage1
            assert msg["stage2"] == stage2
            assert msg["stage3"] == stage3

    def test_add_assistant_message_nonexistent(self, temp_dir):
        """Test adding assistant message to non-existent conversation."""
        data_dir = temp_dir / "conversations"
        data_dir.mkdir()

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            with pytest.raises(ValueError, match="not found"):
                add_assistant_message("nonexistent", [], [], {})


# ============================================================================
# UPDATE CONVERSATION TITLE
# ============================================================================

class TestUpdateConversationTitle:
    """Test update_conversation_title function."""

    def test_update_title(self, temp_dir):
        """Test updating conversation title."""
        data_dir = temp_dir / "conversations"
        data_dir.mkdir()

        # Create initial conversation
        conv_data = {
            "id": "title-test",
            "title": "Original Title",
            "messages": [],
            "created_at": "2024-01-01T00:00:00"
        }
        with open(data_dir / "title-test.json", "w") as f:
            json.dump(conv_data, f)

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            update_conversation_title("title-test", "New Title")

            conversation = get_conversation("title-test")
            assert conversation["title"] == "New Title"

    def test_update_title_nonexistent(self, temp_dir):
        """Test updating title of non-existent conversation."""
        data_dir = temp_dir / "conversations"
        data_dir.mkdir()

        with patch('synod.core.storage.DATA_DIR', str(data_dir)):
            with pytest.raises(ValueError, match="not found"):
                update_conversation_title("nonexistent", "New Title")
