"""Syntax highlighting utilities for Synod output.

Parses markdown-style code blocks and applies Rich syntax highlighting.
"""

import re
from typing import List, Tuple
from rich.console import Console, Group
from rich.syntax import Syntax
from rich.text import Text
from rich.markdown import Markdown


# Language aliases for syntax highlighting
LANGUAGE_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "rb": "ruby",
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "yml": "yaml",
    "md": "markdown",
    "dockerfile": "docker",
    "rs": "rust",
    "kt": "kotlin",
    "cs": "csharp",
    "c++": "cpp",
    "h": "c",
    "hpp": "cpp",
    "jsx": "javascript",
    "tsx": "typescript",
    "vue": "html",
    "svelte": "html",
}


def normalize_language(lang: str) -> str:
    """Normalize language name for syntax highlighting."""
    lang = lang.lower().strip()
    return LANGUAGE_ALIASES.get(lang, lang)


def parse_code_blocks(text: str) -> List[Tuple[str, str, str]]:
    """Parse text and extract code blocks with their languages.

    Args:
        text: Text containing markdown-style code blocks

    Returns:
        List of tuples: (type, content, language)
        - type is 'text' or 'code'
        - content is the actual text/code
        - language is the code language (empty for text)
    """
    # Pattern to match ```language\ncode\n``` blocks
    pattern = r"```(\w*)\n(.*?)```"

    parts = []
    last_end = 0

    for match in re.finditer(pattern, text, re.DOTALL):
        # Add text before this code block
        if match.start() > last_end:
            before_text = text[last_end : match.start()]
            if before_text.strip():
                parts.append(("text", before_text, ""))

        # Add the code block
        language = match.group(1) or "text"
        code = match.group(2)
        parts.append(("code", code, normalize_language(language)))

        last_end = match.end()

    # Add remaining text after last code block
    if last_end < len(text):
        remaining = text[last_end:]
        if remaining.strip():
            parts.append(("text", remaining, ""))

    # If no code blocks found, return the whole text as text
    if not parts:
        parts.append(("text", text, ""))

    return parts


def render_with_syntax(text: str, console: Console = None) -> Group:
    """Render text with syntax-highlighted code blocks.

    Args:
        text: Text containing markdown-style code blocks
        console: Optional console for rendering

    Returns:
        Rich Group containing rendered content
    """
    parts = parse_code_blocks(text)
    renderables = []

    for part_type, content, language in parts:
        if part_type == "code":
            # Create syntax-highlighted code block
            syntax = Syntax(
                content.rstrip(),
                language,
                theme="monokai",
                line_numbers=False,
                word_wrap=True,
                background_color="default",
            )
            renderables.append(syntax)
        else:
            # Regular text - use Text for proper styling
            # But first, handle inline code with backticks
            renderables.append(Text.from_markup(content.strip()))

    return Group(*renderables)


def format_response_with_syntax(text: str) -> str:
    """Format response text, highlighting code blocks for Rich console.

    This returns markup that Rich can render with syntax highlighting.
    For use when you need a string rather than renderables.

    Args:
        text: Text containing markdown-style code blocks

    Returns:
        Text with Rich markup for code blocks
    """
    # For simple cases, we can use Rich's Markdown renderer
    # which handles code blocks automatically
    return text


def print_with_syntax(text: str, console: Console = None):
    """Print text with syntax-highlighted code blocks.

    Args:
        text: Text containing markdown-style code blocks
        console: Console to print to (uses default if None)
    """
    if console is None:
        console = Console()

    parts = parse_code_blocks(text)

    for part_type, content, language in parts:
        if part_type == "code":
            # Create syntax-highlighted code block
            syntax = Syntax(
                content.rstrip(),
                language,
                theme="monokai",
                line_numbers=False,
                word_wrap=True,
                background_color="default",
            )
            console.print(syntax)
        else:
            # Regular text
            console.print(content.strip())


class SyntaxMarkdown(Markdown):
    """Enhanced Markdown renderer with better syntax highlighting."""

    def __init__(self, markup: str, **kwargs):
        # Set code theme
        kwargs.setdefault("code_theme", "monokai")
        super().__init__(markup, **kwargs)
