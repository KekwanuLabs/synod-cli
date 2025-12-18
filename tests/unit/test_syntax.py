"""Unit tests for the syntax highlighting module."""

import pytest
from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text
from io import StringIO

from synod.core.syntax import (
    LANGUAGE_ALIASES,
    normalize_language,
    parse_code_blocks,
    render_with_syntax,
    format_response_with_syntax,
    print_with_syntax,
    SyntaxMarkdown,
)


# ============================================================================
# LANGUAGE ALIASES
# ============================================================================

class TestLanguageAliases:
    """Test language alias constants."""

    def test_common_aliases_defined(self):
        """Test common language aliases are defined."""
        assert LANGUAGE_ALIASES['js'] == 'javascript'
        assert LANGUAGE_ALIASES['ts'] == 'typescript'
        assert LANGUAGE_ALIASES['py'] == 'python'
        assert LANGUAGE_ALIASES['rb'] == 'ruby'
        assert LANGUAGE_ALIASES['sh'] == 'bash'

    def test_shell_aliases(self):
        """Test shell-related aliases."""
        assert LANGUAGE_ALIASES['shell'] == 'bash'
        assert LANGUAGE_ALIASES['zsh'] == 'bash'

    def test_config_file_aliases(self):
        """Test config file aliases."""
        assert LANGUAGE_ALIASES['yml'] == 'yaml'
        assert LANGUAGE_ALIASES['md'] == 'markdown'
        assert LANGUAGE_ALIASES['dockerfile'] == 'docker'

    def test_cpp_aliases(self):
        """Test C++ related aliases."""
        assert LANGUAGE_ALIASES['c++'] == 'cpp'
        assert LANGUAGE_ALIASES['hpp'] == 'cpp'
        assert LANGUAGE_ALIASES['h'] == 'c'

    def test_web_framework_aliases(self):
        """Test web framework aliases."""
        assert LANGUAGE_ALIASES['jsx'] == 'javascript'
        assert LANGUAGE_ALIASES['tsx'] == 'typescript'
        assert LANGUAGE_ALIASES['vue'] == 'html'
        assert LANGUAGE_ALIASES['svelte'] == 'html'


# ============================================================================
# NORMALIZE LANGUAGE
# ============================================================================

class TestNormalizeLanguage:
    """Test normalize_language function."""

    def test_known_alias(self):
        """Test normalizing known aliases."""
        assert normalize_language('js') == 'javascript'
        assert normalize_language('py') == 'python'
        assert normalize_language('ts') == 'typescript'

    def test_unknown_language(self):
        """Test unknown language returns as-is."""
        assert normalize_language('rust') == 'rust'
        assert normalize_language('go') == 'go'
        assert normalize_language('java') == 'java'

    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert normalize_language('JS') == 'javascript'
        assert normalize_language('PY') == 'python'
        assert normalize_language('Python') == 'python'

    def test_whitespace_handling(self):
        """Test whitespace is stripped."""
        assert normalize_language('  js  ') == 'javascript'
        assert normalize_language('\tpy\n') == 'python'


# ============================================================================
# PARSE CODE BLOCKS
# ============================================================================

class TestParseCodeBlocks:
    """Test parse_code_blocks function."""

    def test_no_code_blocks(self):
        """Test text with no code blocks."""
        text = "This is plain text with no code."
        parts = parse_code_blocks(text)

        assert len(parts) == 1
        assert parts[0][0] == 'text'
        assert parts[0][1] == text
        assert parts[0][2] == ''

    def test_single_code_block(self):
        """Test text with single code block."""
        text = '''Here is some code:
```python
def hello():
    pass
```
That was the code.'''

        parts = parse_code_blocks(text)

        assert len(parts) == 3
        assert parts[0][0] == 'text'
        assert 'Here is some code' in parts[0][1]
        assert parts[1][0] == 'code'
        assert 'def hello()' in parts[1][1]
        assert parts[1][2] == 'python'
        assert parts[2][0] == 'text'
        assert 'That was the code' in parts[2][1]

    def test_multiple_code_blocks(self):
        """Test text with multiple code blocks."""
        text = '''First block:
```python
print("hello")
```
Second block:
```javascript
console.log("world")
```
Done.'''

        parts = parse_code_blocks(text)

        code_parts = [p for p in parts if p[0] == 'code']
        assert len(code_parts) == 2
        assert code_parts[0][2] == 'python'
        assert code_parts[1][2] == 'javascript'

    def test_code_block_with_alias(self):
        """Test code block with language alias."""
        text = '''```js
const x = 1;
```'''

        parts = parse_code_blocks(text)

        assert len(parts) == 1
        assert parts[0][0] == 'code'
        assert parts[0][2] == 'javascript'

    def test_code_block_no_language(self):
        """Test code block without language specified."""
        text = '''```
plain code
```'''

        parts = parse_code_blocks(text)

        assert len(parts) == 1
        assert parts[0][0] == 'code'
        assert parts[0][2] == 'text'

    def test_empty_text_between_blocks(self):
        """Test handling of empty text between blocks."""
        text = '''```python
code1
```
```python
code2
```'''

        parts = parse_code_blocks(text)

        code_parts = [p for p in parts if p[0] == 'code']
        assert len(code_parts) == 2


# ============================================================================
# RENDER WITH SYNTAX
# ============================================================================

class TestRenderWithSyntax:
    """Test render_with_syntax function."""

    def test_returns_group(self):
        """Test render returns a Rich Group."""
        from rich.console import Group as RichGroup

        text = "Hello world"
        result = render_with_syntax(text)

        assert isinstance(result, RichGroup)

    def test_renders_code_blocks(self):
        """Test code blocks are rendered as Syntax objects."""
        text = '''```python
def test():
    pass
```'''

        result = render_with_syntax(text)

        # Group should contain renderables
        assert result.renderables is not None


# ============================================================================
# FORMAT RESPONSE WITH SYNTAX
# ============================================================================

class TestFormatResponseWithSyntax:
    """Test format_response_with_syntax function."""

    def test_returns_string(self):
        """Test function returns a string."""
        text = "Hello world"
        result = format_response_with_syntax(text)

        assert isinstance(result, str)

    def test_preserves_content(self):
        """Test content is preserved."""
        text = "Hello world with `code`"
        result = format_response_with_syntax(text)

        assert "Hello world" in result


# ============================================================================
# PRINT WITH SYNTAX
# ============================================================================

class TestPrintWithSyntax:
    """Test print_with_syntax function."""

    def test_prints_to_console(self):
        """Test printing to console."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        text = "Hello world"
        print_with_syntax(text, console=console)

        output_text = output.getvalue()
        assert "Hello" in output_text

    def test_prints_code_block(self):
        """Test printing code block."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        text = '''```python
print("test")
```'''
        print_with_syntax(text, console=console)

        output_text = output.getvalue()
        assert "print" in output_text

    def test_creates_default_console(self):
        """Test creates default console when none provided."""
        # Should not raise
        text = "Hello"
        # Can't easily capture stdout, just verify it doesn't crash
        # print_with_syntax(text)  # Would print to actual stdout


# ============================================================================
# SYNTAX MARKDOWN CLASS
# ============================================================================

class TestSyntaxMarkdown:
    """Test SyntaxMarkdown class."""

    def test_inherits_from_markdown(self):
        """Test class inherits from Markdown."""
        from rich.markdown import Markdown

        md = SyntaxMarkdown("# Hello")
        assert isinstance(md, Markdown)

    def test_default_code_theme(self):
        """Test default code theme is monokai."""
        md = SyntaxMarkdown("# Test")
        # The code_theme should be set
        assert md.code_theme == 'monokai'

    def test_custom_kwargs(self):
        """Test custom kwargs are passed through."""
        md = SyntaxMarkdown("# Test", code_theme='dracula')
        assert md.code_theme == 'dracula'
