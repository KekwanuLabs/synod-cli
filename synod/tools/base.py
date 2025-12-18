"""Base classes for Synod tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from enum import Enum


class ToolStatus(Enum):
    """Status of tool execution."""

    SUCCESS = "success"
    ERROR = "error"
    CONFIRMATION_REQUIRED = "confirmation_required"
    CANCELLED = "cancelled"


@dataclass
class ToolResult:
    """Result of a tool execution."""

    status: ToolStatus
    output: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API transmission."""
        return {
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class ConfirmationRequired:
    """Raised when user confirmation is needed before tool execution."""

    tool_name: str
    operation: str
    description: str
    details: Optional[str] = None
    diff: Optional[str] = None  # For file edits


class SessionFlags:
    """Flags to control confirmation behavior for a session."""

    def __init__(self):
        self.auto_approve_file_ops = False
        self.auto_approve_bash = False
        self.auto_approve_all = False

    def should_confirm(self, tool_type: str) -> bool:
        """Check if confirmation is needed for this tool type."""
        if self.auto_approve_all:
            return False
        if tool_type == "bash" and self.auto_approve_bash:
            return False
        if tool_type in ["create_file", "edit_file"] and self.auto_approve_file_ops:
            return False
        return True


class Tool(ABC):
    """Base class for all Synod tools."""

    name: str = "base_tool"
    description: str = "Base tool"
    requires_confirmation: bool = False

    def __init__(
        self, working_directory: str, session_flags: Optional[SessionFlags] = None
    ):
        self.working_directory = working_directory
        self.session_flags = session_flags or SessionFlags()

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def get_confirmation_info(self, **kwargs) -> Optional[ConfirmationRequired]:
        """Get confirmation info if this operation needs user approval.

        Override in subclasses that need confirmation.
        """
        return None

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """Get the JSON schema for this tool's parameters.

        Override in subclasses.
        """
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @classmethod
    def get_tool_definition(cls) -> Dict[str, Any]:
        """Get the full tool definition for the AI."""
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.get_schema(),
        }
