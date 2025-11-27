"""Synod color system and Rich theme configuration.

This module defines the visual identity of Synod - colors, styles, and Rich themes
used throughout the application.
"""

from typing import List
from rich.theme import Theme
from rich.style import Style

# ============================================================================
# SYNOD COLOR PALETTE
# ============================================================================
# Inspired by the energy of debate and authority of the church councils

# Primary: Bright Orange - Energy, debate, intellectual fire
PRIMARY = "#FF6B35"

# Secondary: Deep Purple - Authority, wisdom, papal decisions
SECONDARY = "#7C3AED"

# Accent: Pink - Conflict, passion, critical reviews
ACCENT = "#EC4899"

# Supporting Colors
CYAN = "#06B6D4"      # Bishop proposals, information
GOLD = "#FBBF24"      # Success, completed actions
GREEN = "#10B981"     # Confirmations, positive results
RED = "#EF4444"       # Errors, high disagreement
GRAY = "#6B7280"      # Dim text, metadata

# ============================================================================
# RICH THEME
# ============================================================================

SYNOD_THEME = Theme({
    # Core Brand Colors
    "primary": PRIMARY,
    "secondary": SECONDARY,
    "accent": ACCENT,

    # Semantic Colors
    "info": CYAN,
    "success": GREEN,
    "warning": GOLD,
    "error": RED,
    "dim": GRAY,

    # Debate Roles
    "bishop": f"bold {CYAN}",
    "pope": f"bold {SECONDARY}",
    "dissent": f"bold {ACCENT}",

    # UI Elements
    "prompt": PRIMARY,
    "highlight": f"bold {PRIMARY}",
    "title": f"bold {SECONDARY}",
    "subtitle": CYAN,
    "code": "#A78BFA",  # Light purple for code

    # Status Indicators
    "status.active": f"bold {PRIMARY}",
    "status.complete": f"bold {GREEN}",
    "status.error": f"bold {RED}",
    "status.pending": GRAY,

    # Progress & Metrics
    "progress.percentage": PRIMARY,
    "progress.complete": GREEN,
    "progress.remaining": GRAY,
    "cost": GOLD,
    "tokens": CYAN,
})

# ============================================================================
# STYLE PRESETS
# ============================================================================

class SynodStyles:
    """Pre-configured Rich styles for common use cases."""

    # Headers and Titles
    LOGO = Style(color=PRIMARY, bold=True)
    TITLE = Style(color=SECONDARY, bold=True)
    SUBTITLE = Style(color=CYAN)

    # Debate Roles
    BISHOP = Style(color=CYAN, bold=True)
    POPE = Style(color=SECONDARY, bold=True)
    DISSENT = Style(color=ACCENT, bold=True)

    # Status Messages
    SUCCESS = Style(color=GREEN, bold=True)
    WARNING = Style(color=GOLD, bold=True)
    ERROR = Style(color=RED, bold=True)
    INFO = Style(color=CYAN)

    # UI Elements
    PROMPT = Style(color=PRIMARY, bold=True)
    HIGHLIGHT = Style(color=PRIMARY, bold=True)
    DIM = Style(color=GRAY, dim=True)
    TAGLINE = Style(color=GRAY)  # Brighter than DIM (no dim=True)
    CODE = Style(color="#A78BFA")

    # Metrics
    COST = Style(color=GOLD)
    TOKENS = Style(color=CYAN)
    PERCENTAGE = Style(color=PRIMARY)

# ============================================================================
# PANEL STYLES
# ============================================================================

# Border styles for different panel types
BORDER_STYLE_BISHOP = CYAN
BORDER_STYLE_POPE = SECONDARY
BORDER_STYLE_DISSENT = ACCENT
BORDER_STYLE_SUCCESS = GREEN
BORDER_STYLE_ERROR = RED
BORDER_STYLE_INFO = CYAN
BORDER_STYLE_PRIMARY = PRIMARY

# ============================================================================
# PROGRESS BAR STYLES
# ============================================================================

# Custom progress bar colors
PROGRESS_BAR_COMPLETE = f"bar.complete"
PROGRESS_BAR_FINISHED = f"bar.finished"
PROGRESS_BAR_PULSE = f"bar.pulse"

# Progress bar gradient: Orange → Purple
PROGRESS_GRADIENT = [PRIMARY, ACCENT, SECONDARY]

# ============================================================================
# ASCII ART COLORS
# ============================================================================

# Logo uses gradient effect
LOGO_COLORS = [
    "#FF6B35",  # Bright Orange
    "#FF5E8A",  # Orange-Pink transition
    "#E651D5",  # Pink-Purple transition
    "#7C3AED",  # Deep Purple
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_role_color(role: str) -> str:
    """Get color for a specific debate role.

    Args:
        role: One of 'bishop', 'pope', 'dissent', 'user'

    Returns:
        Hex color code
    """
    role_colors = {
        "bishop": CYAN,
        "pope": SECONDARY,
        "dissent": ACCENT,
        "user": PRIMARY,
    }
    return role_colors.get(role.lower(), CYAN)

def get_status_color(status: str) -> str:
    """Get color for a status indicator.

    Args:
        status: One of 'success', 'error', 'warning', 'info', 'pending'

    Returns:
        Hex color code
    """
    status_colors = {
        "success": GREEN,
        "error": RED,
        "warning": GOLD,
        "info": CYAN,
        "pending": GRAY,
        "active": PRIMARY,
    }
    return status_colors.get(status.lower(), CYAN)

def gradient_text(text: str, colors: List[str]) -> str:
    """Apply a color gradient to text.

    Args:
        text: Text to colorize
        colors: List of hex color codes for the gradient

    Returns:
        Rich markup string with gradient applied
    """
    if len(colors) == 0:
        return text
    if len(colors) == 1:
        return f"[{colors[0]}]{text}[/]"

    # Calculate color per character
    chars = list(text)
    n_chars = len(chars)
    n_colors = len(colors)

    if n_chars == 0:
        return text

    result = []
    for i, char in enumerate(chars):
        # Calculate which color to use
        color_index = int((i / n_chars) * (n_colors - 1))
        color = colors[color_index]
        result.append(f"[{color}]{char}[/]")

    return "".join(result)

# ============================================================================
# EMOJI SETS
# ============================================================================

# Consistent emoji usage throughout Synod
EMOJI = {
    # Debate roles
    "bishop": "🎓",
    "pope": "⚖️",
    "council": "🏛️",

    # Actions
    "debate": "💭",
    "critique": "🔍",
    "synthesis": "✨",
    "proposal": "💡",

    # Status
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "loading": "⏳",
    "complete": "🎯",

    # Metrics
    "cost": "💰",
    "tokens": "📊",
    "time": "🕐",
    "files": "📁",
    "project": "📦",

    # Navigation
    "enter": "↵",
    "exit": "🚪",
    "help": "❓",
}

def emoji(key: str) -> str:
    """Get emoji for a specific key.

    Args:
        key: Emoji key from EMOJI dict

    Returns:
        Emoji character or empty string if not found
    """
    return EMOJI.get(key.lower(), "")

def format_model_name(model_id: str) -> str:
    """Format raw model ID into clean, user-friendly display name.

    Examples:
        - "anthropic/claude-opus-4.5" → "Claude Opus 4.5"
        - "qwen/qwen-2.5-coder-32b-instruct:free" → "Qwen 2.5 Coder 32B"
        - "openai/gpt-5.1-chat-v3.1" → "GPT 5.1 Chat"

    Args:
        model_id: Raw model identifier (provider/model format)

    Returns:
        Clean display name
    """
    import re

    # Mapping of raw model IDs to clean display names
    CLEAN_NAMES = {
        # Bishops (actual debate models)
        "anthropic/claude-opus-4.5": "Claude Opus 4.5",
        "anthropic/claude-sonnet-4.5": "Claude Sonnet 4.5",
        "openai/gpt-5.1-chat": "GPT 5.1 Chat",
        "openai/gpt-5.1-chat-v3.1": "GPT 5.1 Chat",
        "x-ai/grok-4.1-fast": "Grok 4.1 Fast",
        "x-ai/grok-4.1-fast:free": "Grok 4.1 Fast",
        "google/gemini-3.0": "Gemini 3.0",
        "deepseek/deepseek-v3.1": "DeepSeek V3.1",
        "deepseek/deepseek-chat-v3.1": "DeepSeek V3.1",

        # Classifiers (should not appear as bishops, but handle just in case)
        "qwen/qwen-2.5-coder-32b-instruct": "Qwen 2.5 Coder 32B",
        "qwen/qwen-2.5-coder-32b-instruct:free": "Qwen 2.5 Coder 32B",
        "mistralai/mistral-small-3": "Mistral Small 3",
        "mistralai/mistral-small-3:free": "Mistral Small 3",
        "google/gemma-3-12b": "Gemma 3 12B",
        "google/gemma-3-12b:free": "Gemma 3 12B",
    }

    # Try exact match first
    if model_id in CLEAN_NAMES:
        return CLEAN_NAMES[model_id]

    # Fallback: basic cleanup
    # Remove provider prefix
    name = model_id.split('/', 1)[-1] if '/' in model_id else model_id
    # Remove :free suffix
    name = name.replace(':free', '')
    # Remove version suffixes like -v3.1
    name = re.sub(r'-v\d+(\.\d+)?$', '', name)
    # Remove -chat suffix
    name = name.replace('-chat', '')
    # Capitalize words
    name = ' '.join(word.capitalize() for word in name.replace('-', ' ').split())
    return name
