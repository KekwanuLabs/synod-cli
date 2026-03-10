"""Unit tests for the theme module."""

import pytest

from synod.core.theme import (
    # Colors
    PRIMARY, SECONDARY, ACCENT, CYAN, GOLD, GREEN, RED, GRAY,
    # Theme
    SYNOD_THEME,
    # Style class
    SynodStyles,
    # Border styles
    BORDER_STYLE_BISHOP, BORDER_STYLE_POPE, BORDER_STYLE_DISSENT,
    BORDER_STYLE_SUCCESS, BORDER_STYLE_ERROR, BORDER_STYLE_INFO,
    # Progress
    PROGRESS_GRADIENT, LOGO_COLORS,
    # Emoji
    EMOJI,
    # Functions
    get_role_color,
    get_status_color,
    gradient_text,
    emoji,
    format_model_name,
)


# ============================================================================
# COLOR CONSTANTS
# ============================================================================

class TestColorConstants:
    """Test color constant definitions."""

    def test_primary_color_defined(self):
        """Test primary color is defined as hex."""
        assert PRIMARY == "#FF6B35"
        assert PRIMARY.startswith("#")

    def test_secondary_color_defined(self):
        """Test secondary color is defined as hex."""
        assert SECONDARY == "#7C3AED"
        assert SECONDARY.startswith("#")

    def test_accent_color_defined(self):
        """Test accent color is defined as hex."""
        assert ACCENT == "#EC4899"
        assert ACCENT.startswith("#")

    def test_supporting_colors_defined(self):
        """Test supporting colors are defined."""
        assert CYAN == "#06B6D4"
        assert GOLD == "#FBBF24"
        assert GREEN == "#10B981"
        assert RED == "#EF4444"
        assert GRAY == "#6B7280"


# ============================================================================
# RICH THEME
# ============================================================================

class TestSynodTheme:
    """Test SYNOD_THEME configuration."""

    def test_theme_has_core_colors(self):
        """Test theme defines core brand colors."""
        assert "primary" in SYNOD_THEME.styles
        assert "secondary" in SYNOD_THEME.styles
        assert "accent" in SYNOD_THEME.styles

    def test_theme_has_semantic_colors(self):
        """Test theme defines semantic colors."""
        assert "info" in SYNOD_THEME.styles
        assert "success" in SYNOD_THEME.styles
        assert "warning" in SYNOD_THEME.styles
        assert "error" in SYNOD_THEME.styles
        assert "dim" in SYNOD_THEME.styles

    def test_theme_has_debate_roles(self):
        """Test theme defines debate role styles."""
        assert "bishop" in SYNOD_THEME.styles
        assert "pope" in SYNOD_THEME.styles
        assert "dissent" in SYNOD_THEME.styles

    def test_theme_has_ui_elements(self):
        """Test theme defines UI element styles."""
        assert "prompt" in SYNOD_THEME.styles
        assert "highlight" in SYNOD_THEME.styles
        assert "title" in SYNOD_THEME.styles
        assert "code" in SYNOD_THEME.styles

    def test_theme_has_status_indicators(self):
        """Test theme defines status indicators."""
        assert "status.active" in SYNOD_THEME.styles
        assert "status.complete" in SYNOD_THEME.styles
        assert "status.error" in SYNOD_THEME.styles
        assert "status.pending" in SYNOD_THEME.styles


# ============================================================================
# SYNOD STYLES CLASS
# ============================================================================

class TestSynodStyles:
    """Test SynodStyles class."""

    def test_header_styles_exist(self):
        """Test header/title styles are defined."""
        assert SynodStyles.LOGO is not None
        assert SynodStyles.TITLE is not None
        assert SynodStyles.SUBTITLE is not None

    def test_debate_role_styles_exist(self):
        """Test debate role styles are defined."""
        assert SynodStyles.BISHOP is not None
        assert SynodStyles.POPE is not None
        assert SynodStyles.DISSENT is not None

    def test_status_styles_exist(self):
        """Test status message styles are defined."""
        assert SynodStyles.SUCCESS is not None
        assert SynodStyles.WARNING is not None
        assert SynodStyles.ERROR is not None
        assert SynodStyles.INFO is not None

    def test_ui_styles_exist(self):
        """Test UI element styles are defined."""
        assert SynodStyles.PROMPT is not None
        assert SynodStyles.HIGHLIGHT is not None
        assert SynodStyles.DIM is not None
        assert SynodStyles.CODE is not None

    def test_metric_styles_exist(self):
        """Test metric styles are defined."""
        assert SynodStyles.COST is not None
        assert SynodStyles.TOKENS is not None
        assert SynodStyles.PERCENTAGE is not None


# ============================================================================
# BORDER STYLES
# ============================================================================

class TestBorderStyles:
    """Test panel border style constants."""

    def test_border_styles_are_colors(self):
        """Test border styles are hex colors."""
        assert BORDER_STYLE_BISHOP == CYAN
        assert BORDER_STYLE_POPE == SECONDARY
        assert BORDER_STYLE_DISSENT == ACCENT
        assert BORDER_STYLE_SUCCESS == GREEN
        assert BORDER_STYLE_ERROR == RED
        assert BORDER_STYLE_INFO == CYAN


# ============================================================================
# PROGRESS AND LOGO
# ============================================================================

class TestProgressAndLogo:
    """Test progress bar and logo configurations."""

    def test_progress_gradient_defined(self):
        """Test progress gradient is a list of colors."""
        assert isinstance(PROGRESS_GRADIENT, list)
        assert len(PROGRESS_GRADIENT) == 3
        assert PRIMARY in PROGRESS_GRADIENT

    def test_logo_colors_defined(self):
        """Test logo colors are a list of hex colors."""
        assert isinstance(LOGO_COLORS, list)
        assert len(LOGO_COLORS) == 4
        for color in LOGO_COLORS:
            assert color.startswith("#")


# ============================================================================
# GET_ROLE_COLOR FUNCTION
# ============================================================================

class TestGetRoleColor:
    """Test get_role_color function."""

    def test_bishop_role(self):
        """Test bishop role returns cyan."""
        assert get_role_color("bishop") == CYAN

    def test_pope_role(self):
        """Test pope role returns secondary."""
        assert get_role_color("pope") == SECONDARY

    def test_dissent_role(self):
        """Test dissent role returns accent."""
        assert get_role_color("dissent") == ACCENT

    def test_user_role(self):
        """Test user role returns primary."""
        assert get_role_color("user") == PRIMARY

    def test_case_insensitive(self):
        """Test role lookup is case-insensitive."""
        assert get_role_color("BISHOP") == CYAN
        assert get_role_color("Pope") == SECONDARY
        assert get_role_color("DISSENT") == ACCENT

    def test_unknown_role_returns_default(self):
        """Test unknown role returns default cyan."""
        assert get_role_color("unknown") == CYAN
        assert get_role_color("random") == CYAN


# ============================================================================
# GET_STATUS_COLOR FUNCTION
# ============================================================================

class TestGetStatusColor:
    """Test get_status_color function."""

    def test_success_status(self):
        """Test success status returns green."""
        assert get_status_color("success") == GREEN

    def test_error_status(self):
        """Test error status returns red."""
        assert get_status_color("error") == RED

    def test_warning_status(self):
        """Test warning status returns gold."""
        assert get_status_color("warning") == GOLD

    def test_info_status(self):
        """Test info status returns cyan."""
        assert get_status_color("info") == CYAN

    def test_pending_status(self):
        """Test pending status returns gray."""
        assert get_status_color("pending") == GRAY

    def test_active_status(self):
        """Test active status returns primary."""
        assert get_status_color("active") == PRIMARY

    def test_case_insensitive(self):
        """Test status lookup is case-insensitive."""
        assert get_status_color("SUCCESS") == GREEN
        assert get_status_color("Error") == RED

    def test_unknown_status_returns_default(self):
        """Test unknown status returns default cyan."""
        assert get_status_color("unknown") == CYAN


# ============================================================================
# GRADIENT_TEXT FUNCTION
# ============================================================================

class TestGradientText:
    """Test gradient_text function."""

    def test_empty_colors_returns_text(self):
        """Test empty color list returns original text."""
        result = gradient_text("hello", [])
        assert result == "hello"

    def test_single_color(self):
        """Test single color wraps entire text."""
        result = gradient_text("hello", ["#FF0000"])
        assert result == "[#FF0000]hello[/]"

    def test_multiple_colors_applies_gradient(self):
        """Test multiple colors create gradient markup."""
        # Use longer text to see gradient effect
        result = gradient_text("abcdef", ["#FF0000", "#00FF00"])
        assert "[#FF0000]" in result
        # Last characters should use second color
        assert "a" in result
        assert "f" in result
        # Should have markup tags
        assert "[/]" in result

    def test_empty_text(self):
        """Test empty text returns empty string."""
        result = gradient_text("", ["#FF0000", "#00FF00"])
        assert result == ""

    def test_gradient_with_logo_colors(self):
        """Test gradient with LOGO_COLORS."""
        result = gradient_text("SYNOD", LOGO_COLORS)
        assert "[#FF6B35]" in result  # First color
        assert "S" in result
        assert "Y" in result


# ============================================================================
# EMOJI FUNCTION
# ============================================================================

class TestEmoji:
    """Test emoji function."""

    def test_known_emoji_keys(self):
        """Test known emoji keys return correct emoji."""
        assert emoji("bishop") == "🎓"
        assert emoji("pope") == "⚖️"
        assert emoji("success") == "✅"
        assert emoji("error") == "❌"
        assert emoji("warning") == "⚠️"

    def test_case_insensitive(self):
        """Test emoji lookup is case-insensitive."""
        assert emoji("BISHOP") == "🎓"
        assert emoji("Pope") == "⚖️"
        assert emoji("SUCCESS") == "✅"

    def test_unknown_key_returns_empty(self):
        """Test unknown key returns empty string."""
        assert emoji("unknown") == ""
        assert emoji("random") == ""

    def test_all_emoji_dict_entries(self):
        """Test all EMOJI dict entries are accessible."""
        for key in EMOJI:
            result = emoji(key)
            assert result == EMOJI[key]


# ============================================================================
# FORMAT_MODEL_NAME FUNCTION
# ============================================================================

class TestFormatModelName:
    """Test format_model_name function."""

    def test_known_model_exact_match(self):
        """Test known model IDs return clean names."""
        assert format_model_name("anthropic/claude-opus-4.6") == "Claude Opus 4.6"
        assert format_model_name("openai/gpt-5.4") == "GPT 5.4"
        assert format_model_name("x-ai/grok-4.1-fast") == "Grok 4.1 Fast"

    def test_model_with_free_suffix(self):
        """Test models with :free suffix."""
        assert format_model_name("x-ai/grok-4.1-fast:free") == "Grok 4.1 Fast"
        assert format_model_name("qwen/qwen-2.5-coder-32b-instruct:free") == "Qwen 2.5 Coder 32B"

    def test_model_with_version_suffix(self):
        """Test models with version suffix."""
        assert format_model_name("openai/gpt-5.1-chat-v3.1") == "GPT 5.1 Chat"

    def test_unknown_model_fallback(self):
        """Test unknown model uses fallback cleanup."""
        result = format_model_name("provider/some-new-model:free")
        assert "Some New Model" in result
        assert ":free" not in result
        assert "provider" not in result

    def test_model_without_provider(self):
        """Test model ID without provider prefix."""
        result = format_model_name("some-model-name")
        assert "Some Model Name" in result

    def test_gemini_model(self):
        """Test Google Gemini model."""
        assert format_model_name("google/gemini-3.1-pro-preview") == "Gemini 3.1 Pro"

    def test_deepseek_models(self):
        """Test DeepSeek models."""
        assert format_model_name("deepseek/deepseek-v3.1") == "DeepSeek V3.1"
        assert format_model_name("deepseek/deepseek-chat-v3.1") == "DeepSeek V3.1"

    def test_new_openai_models(self):
        """Test new OpenAI model names."""
        assert format_model_name("openai/gpt-5.4-pro") == "GPT 5.4 Pro"
        assert format_model_name("openai/gpt-5") == "GPT 5"
        assert format_model_name("openai/gpt-5-mini") == "GPT 5 Mini"
        assert format_model_name("openai/gpt-5-nano") == "GPT 5 Nano"

    def test_new_anthropic_models(self):
        """Test new Anthropic model names."""
        assert format_model_name("anthropic/claude-sonnet-4.6") == "Claude Sonnet 4.6"
        assert format_model_name("anthropic/claude-haiku-4.5") == "Claude Haiku 4.5"

    def test_classifier_models(self):
        """Test classifier model names."""
        assert format_model_name("mistralai/mistral-small-3") == "Mistral Small 3"
        assert format_model_name("google/gemma-3-12b") == "Gemma 3 12B"


# ============================================================================
# EMOJI DICT
# ============================================================================

class TestEmojiDict:
    """Test EMOJI dictionary completeness."""

    def test_debate_emojis_defined(self):
        """Test debate role emojis are defined."""
        assert "bishop" in EMOJI
        assert "pope" in EMOJI
        assert "council" in EMOJI

    def test_action_emojis_defined(self):
        """Test action emojis are defined."""
        assert "debate" in EMOJI
        assert "critique" in EMOJI
        assert "synthesis" in EMOJI
        assert "proposal" in EMOJI

    def test_status_emojis_defined(self):
        """Test status emojis are defined."""
        assert "success" in EMOJI
        assert "error" in EMOJI
        assert "warning" in EMOJI
        assert "info" in EMOJI
        assert "loading" in EMOJI
        assert "complete" in EMOJI

    def test_metric_emojis_defined(self):
        """Test metric emojis are defined."""
        assert "cost" in EMOJI
        assert "tokens" in EMOJI
        assert "time" in EMOJI
        assert "files" in EMOJI
        assert "project" in EMOJI

    def test_navigation_emojis_defined(self):
        """Test navigation emojis are defined."""
        assert "enter" in EMOJI
        assert "exit" in EMOJI
        assert "help" in EMOJI
