"""Synod Tools - Local tool execution for the AI coding assistant.

These tools are executed locally by the CLI when requested by the cloud AI.
"""

from .base import Tool, ToolResult, ConfirmationRequired
from .bash import BashTool
from .file_editor import FileEditorTool
from .search import SearchTool
from .executor import ToolExecutor, reset_session_auto_approve, set_session_auto_approve

__all__ = [
    'Tool',
    'ToolResult',
    'ConfirmationRequired',
    'BashTool',
    'FileEditorTool',
    'SearchTool',
    'ToolExecutor',
    'reset_session_auto_approve',
    'set_session_auto_approve',
]
