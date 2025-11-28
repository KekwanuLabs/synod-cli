"""Template-based configuration for Synod.

This module handles:
- Loading configuration from .synod.template.yaml
- Validating template structure and values
- Generating .env and config.json from template
- Clear error messages for invalid templates
"""

import os
import yaml
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from .theme import PRIMARY, CYAN, GOLD, GREEN, emoji
from .model_registry import get_available_providers, ModelProvider
from .config import CONFIG_FILE, CONFIG_DIR, CONFIG_YAML, ENV_FILE

console = Console()

# Config file in user home directory (~/.synod-cli/config.yaml)
# This ensures config persists across all project directories
TEMPLATE_FILENAME = "config.yaml"


def get_bundled_template_path() -> Optional[Path]:
    """Get path to bundled template file in package."""
    # Try to find template in package directory
    import synod
    package_dir = Path(synod.__file__).parent.parent
    template_path = package_dir / TEMPLATE_FILENAME

    if template_path.exists():
        return template_path

    return None


def find_template() -> Optional[Path]:
    """Find config file in user home directory (~/.synod-cli/config.yaml)."""
    config_path = Path(CONFIG_YAML)
    if config_path.exists():
        return config_path
    return None


def copy_template_to_home() -> bool:
    """
    Copy bundled template to user home directory (~/.synod-cli/config.yaml).

    Returns:
        True if successful, False otherwise
    """
    config_path = Path(CONFIG_YAML)
    if config_path.exists():
        console.print(f"[warning]Config already exists at {config_path}[/warning]")
        return False

    bundled = get_bundled_template_path()
    if not bundled:
        console.print("[error]Could not find bundled template file[/error]")
        return False

    try:
        import shutil
        os.makedirs(CONFIG_DIR, exist_ok=True)
        shutil.copy(bundled, config_path)
        console.print(f"[success]✓ Created config at {config_path}[/success]")
        console.print(f"[dim]Edit this file to configure Synod, then run 'synod' to start[/dim]")
        return True
    except Exception as e:
        console.print(f"[error]Error copying template: {e}[/error]")
        return False


def is_template_filled() -> bool:
    """Check if template exists and has been filled out (not empty)."""
    template_path = find_template()
    if not template_path:
        return False

    try:
        with open(template_path, 'r') as f:
            config = yaml.safe_load(f)

        if not config or not isinstance(config, dict):
            return False

        # Check if bishops are defined
        bishops = config.get('bishops', [])
        if not bishops or len(bishops) == 0:
            return False

        # Check if mode is set
        mode = config.get('mode')
        if not mode:
            return False

        return True
    except:
        return False


class ValidationError(Exception):
    """Template validation error with user-friendly message."""
    pass


def validate_template(config: Dict) -> Tuple[bool, List[str]]:
    """
    Validate template configuration.

    Returns:
        (is_valid, list_of_errors)
    """
    errors = []

    # 1. Check mode
    mode = config.get('mode')
    if not mode:
        errors.append("❌ 'mode' is required (must be 'simple' or 'mixed')")
    elif mode not in ['simple', 'mixed']:
        errors.append(f"❌ Invalid mode '{mode}' (must be 'simple' or 'mixed')")

    # 2. Check bishops
    bishops = config.get('bishops', [])
    if not bishops:
        errors.append("❌ 'bishops' list is empty (need at least 3 models)")
    elif len(bishops) < 3:
        errors.append(f"❌ Only {len(bishops)} bishops selected (need at least 3)")

    # Validate bishop format
    for bishop in bishops:
        if not isinstance(bishop, str):
            errors.append(f"❌ Invalid bishop format: {bishop} (should be 'provider/model-name')")
        elif '/' not in bishop:
            errors.append(f"❌ Invalid bishop format: '{bishop}' (should be 'provider/model-name')")

    # NOTE: Multiple models from same provider are now allowed
    # Users may want both Opus and Sonnet, or multiple GPT variants
    # for different perspectives despite coming from the same provider

    # 3. Check pope
    pope = config.get('pope')
    if not pope:
        errors.append("❌ 'pope' is required")
    elif pope not in bishops:
        errors.append(f"❌ Pope '{pope}' must be one of the bishops")

    # 4. Mode-specific validation
    if mode == 'simple':
        errors.extend(_validate_simple_mode(config))
    elif mode == 'mixed':
        errors.extend(_validate_mixed_mode(config, bishops))

    return (len(errors) == 0, errors)


def _validate_simple_mode(config: Dict) -> List[str]:
    """Validate simple mode configuration."""
    errors = []

    simple = config.get('simple', {})
    if not simple:
        errors.append("❌ 'simple' section is empty (need to enable one provider)")
        return errors

    enabled_providers = []
    for provider_name, provider_config in simple.items():
        if isinstance(provider_config, dict) and provider_config.get('enabled'):
            enabled_providers.append(provider_name)

            # Check required fields for each provider
            if provider_name == 'openrouter':
                if not provider_config.get('api_key'):
                    errors.append(f"❌ OpenRouter: 'api_key' is required")

            elif provider_name in ['azure_foundry', 'azure_openai']:
                if not provider_config.get('endpoint'):
                    errors.append(f"❌ {provider_name}: 'endpoint' is required")
                if not provider_config.get('api_key'):
                    errors.append(f"❌ {provider_name}: 'api_key' is required")

            elif provider_name == 'google_vertex':
                if not provider_config.get('project_id'):
                    errors.append(f"❌ Google Vertex: 'project_id' is required")
                if not provider_config.get('region'):
                    errors.append(f"❌ Google Vertex: 'region' is required")

            elif provider_name in ['anthropic', 'openai']:
                if not provider_config.get('api_key'):
                    errors.append(f"❌ {provider_name}: 'api_key' is required")

    if len(enabled_providers) == 0:
        errors.append("❌ Simple mode: no provider enabled (enable exactly one)")
    elif len(enabled_providers) > 1:
        errors.append(f"❌ Simple mode: multiple providers enabled ({', '.join(enabled_providers)}) - enable only one")

    return errors


def _validate_mixed_mode(config: Dict, bishops: List[str]) -> List[str]:
    """Validate mixed mode configuration."""
    errors = []

    mixed = config.get('mixed', {})
    if not mixed:
        errors.append("❌ 'mixed' section is empty")
        return errors

    # Check providers section
    providers = mixed.get('providers', {})
    if not providers:
        errors.append("❌ Mixed mode: 'providers' section is empty")
        return errors

    enabled_providers = []
    for provider_name, provider_config in providers.items():
        if isinstance(provider_config, dict) and provider_config.get('enabled'):
            enabled_providers.append(provider_name)

            # Validate credentials (same as simple mode)
            if provider_name == 'openrouter':
                if not provider_config.get('api_key'):
                    errors.append(f"❌ OpenRouter: 'api_key' is required")

            elif provider_name in ['azure_foundry', 'azure_openai']:
                if not provider_config.get('endpoint'):
                    errors.append(f"❌ {provider_name}: 'endpoint' is required")
                if not provider_config.get('api_key'):
                    errors.append(f"❌ {provider_name}: 'api_key' is required")

            elif provider_name == 'google_vertex':
                if not provider_config.get('project_id'):
                    errors.append(f"❌ Google Vertex: 'project_id' is required")

            elif provider_name in ['anthropic', 'openai']:
                if not provider_config.get('api_key'):
                    errors.append(f"❌ {provider_name}: 'api_key' is required")

    if len(enabled_providers) == 0:
        errors.append("❌ Mixed mode: no providers enabled (enable at least one)")

    # Check routing section
    routing = mixed.get('routing', {})
    if not routing:
        errors.append("❌ Mixed mode: 'routing' section is empty")
        return errors

    # Models that are ONLY available on OpenRouter
    OPENROUTER_ONLY_MODELS = [
        "x-ai/grok-4.1-fast:free",
        "x-ai/grok-4.1-fast",
        "z-ai/glm-4.6",
    ]

    # Ensure all bishops have routing entries
    for bishop in bishops:
        if bishop not in routing:
            errors.append(f"❌ Mixed mode: no routing for bishop '{bishop}'")
        else:
            routed_provider = routing[bishop]
            # Check if routed provider is enabled
            if routed_provider not in enabled_providers:
                errors.append(f"❌ Bishop '{bishop}' routed to '{routed_provider}' but that provider is not enabled")

            # Enforce OpenRouter-only models
            if bishop in OPENROUTER_ONLY_MODELS and routed_provider != 'openrouter':
                errors.append(f"❌ Model '{bishop}' is only available on OpenRouter (cannot use '{routed_provider}')")

    return errors


def load_and_validate_template() -> Tuple[bool, Optional[Dict], List[str]]:
    """
    Load and validate template file.

    Returns:
        (is_valid, config_dict, list_of_errors)
    """
    template_path = find_template()

    if not template_path:
        return (False, None, ["Template file not found"])

    try:
        with open(template_path, 'r') as f:
            config = yaml.safe_load(f)

        if not config or not isinstance(config, dict):
            return (False, None, ["Template file is empty or invalid YAML"])

        # Validate
        is_valid, errors = validate_template(config)

        return (is_valid, config, errors)

    except yaml.YAMLError as e:
        return (False, None, [f"YAML syntax error: {e}"])
    except Exception as e:
        return (False, None, [f"Error reading template: {e}"])


def show_validation_errors(errors: List[str]) -> None:
    """Display validation errors in a beautiful panel."""
    error_text = Text()

    error_text.append("Template Validation Failed\n\n", style=f"bold {GOLD}")

    error_text.append("Found the following issues in ", style="dim")
    error_text.append(str(find_template()), style=f"bold {CYAN}")
    error_text.append(":\n\n", style="dim")

    for error in errors:
        error_text.append(f"{error}\n", style="white")

    error_text.append("\n")
    error_text.append("💡 ", style=f"bold {PRIMARY}")
    error_text.append("Fix these issues and try again, or run ", style="dim")
    error_text.append("synod config", style=f"bold {CYAN}")
    error_text.append(" for interactive setup.\n", style="dim")

    panel = Panel(
        error_text,
        title=f"[{GOLD}]⚠️  Configuration Error[/{GOLD}]",
        border_style=GOLD,
    )

    console.print()
    console.print(panel)
    console.print()


def generate_env_from_template(config: Dict) -> str:
    """Generate .env file content from template configuration."""
    lines = []
    lines.append("# Synod Configuration")
    lines.append("# Generated from .synod.template.yaml")
    lines.append("")

    mode = config.get('mode')

    if mode == 'simple':
        # Simple mode: one provider for all
        simple = config.get('simple', {})

        for provider_name, provider_config in simple.items():
            if not isinstance(provider_config, dict) or not provider_config.get('enabled'):
                continue

            lines.append(f"# Provider: {provider_name}")
            lines.append(f"SYNOD_PROVIDER={provider_name}")
            lines.append("")

            # Add provider-specific credentials
            if provider_name == 'openrouter':
                lines.append(f"OPENROUTER_API_KEY={provider_config.get('api_key', '')}")

            elif provider_name == 'azure_foundry':
                lines.append(f"AZURE_FOUNDRY_ENDPOINT={provider_config.get('endpoint', '')}")
                lines.append(f"AZURE_FOUNDRY_API_KEY={provider_config.get('api_key', '')}")

            elif provider_name == 'azure_openai':
                lines.append(f"AZURE_OPENAI_ENDPOINT={provider_config.get('endpoint', '')}")
                lines.append(f"AZURE_OPENAI_API_KEY={provider_config.get('api_key', '')}")

            elif provider_name == 'google_vertex':
                lines.append(f"GOOGLE_CLOUD_PROJECT={provider_config.get('project_id', '')}")
                lines.append(f"GOOGLE_CLOUD_REGION={provider_config.get('region', '')}")

            elif provider_name == 'anthropic':
                lines.append(f"ANTHROPIC_API_KEY={provider_config.get('api_key', '')}")

            elif provider_name == 'openai':
                lines.append(f"OPENAI_API_KEY={provider_config.get('api_key', '')}")

            lines.append("")

    elif mode == 'mixed':
        # Mixed mode: per-model routing
        mixed = config.get('mixed', {})
        providers = mixed.get('providers', {})
        routing = mixed.get('routing', {})

        lines.append("SYNOD_MODE=mixed")
        lines.append("")

        # Add all provider credentials
        for provider_name, provider_config in providers.items():
            if not isinstance(provider_config, dict) or not provider_config.get('enabled'):
                continue

            lines.append(f"# {provider_name.upper()}")

            if provider_name == 'openrouter':
                lines.append(f"OPENROUTER_API_KEY={provider_config.get('api_key', '')}")

            elif provider_name == 'azure_foundry':
                lines.append(f"AZURE_FOUNDRY_ENDPOINT={provider_config.get('endpoint', '')}")
                lines.append(f"AZURE_FOUNDRY_API_KEY={provider_config.get('api_key', '')}")

            elif provider_name == 'azure_openai':
                lines.append(f"AZURE_OPENAI_ENDPOINT={provider_config.get('endpoint', '')}")
                lines.append(f"AZURE_OPENAI_API_KEY={provider_config.get('api_key', '')}")

            elif provider_name == 'google_vertex':
                lines.append(f"GOOGLE_CLOUD_PROJECT={provider_config.get('project_id', '')}")
                lines.append(f"GOOGLE_CLOUD_REGION={provider_config.get('region', '')}")

            elif provider_name == 'anthropic':
                lines.append(f"ANTHROPIC_API_KEY={provider_config.get('api_key', '')}")

            elif provider_name == 'openai':
                lines.append(f"OPENAI_API_KEY={provider_config.get('api_key', '')}")

            lines.append("")

        # Add per-model routing
        lines.append("# Model Routing")
        for model_id, provider in routing.items():
            model_key = model_id.replace('/', '_').replace('-', '_').replace('.', '_').upper()
            lines.append(f"{model_key}_PROVIDER={provider}")

        lines.append("")

    return "\n".join(lines)


def generate_config_from_template(config: Dict) -> Dict:
    """Generate config.json content from template configuration."""
    return {
        "bishop_models": config.get('bishops', []),
        "pope_model": config.get('pope', ''),
        "onboarded": True,
        "version": "2.0.0",
        "source": "template",
        "mode": config.get('mode', 'simple'),
    }


def apply_template_config() -> bool:
    """
    Load template, validate, and apply configuration.

    Returns:
        True if successful, False otherwise
    """
    console.print(f"\n[{CYAN}]Found configuration template: {find_template()}[/{CYAN}]")
    console.print(f"[dim]Validating...[/dim]\n")

    # Load and validate
    is_valid, config, errors = load_and_validate_template()

    if not is_valid:
        show_validation_errors(errors)
        return False

    # Generate .env in user home directory
    env_content = generate_env_from_template(config)
    env_path = Path(ENV_FILE)

    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(env_path, 'w') as f:
        f.write(env_content)

    console.print(f"[success]✓ Generated .env file at ~/.synod-cli/[/success]")

    # Generate config.json
    os.makedirs(CONFIG_DIR, exist_ok=True)
    config_data = generate_config_from_template(config)

    import json
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=2)

    console.print(f"[success]✓ Generated config file[/success]")

    # Show summary
    show_config_summary(config)

    return True


def show_config_summary(config: Dict) -> None:
    """Display configuration summary."""
    text = Text()

    text.append(f"\n{emoji('success')} ", style=GREEN)
    text.append("Configuration Applied!\n\n", style=f"bold {GREEN}")

    # Bishops
    text.append(f"   {emoji('bishop')} Bishops:\n", style=CYAN)
    for bishop in config.get('bishops', []):
        model_name = bishop.split('/')[-1]
        text.append(f"      • {model_name}\n", style="dim")

    # Pope
    pope = config.get('pope', '')
    pope_name = pope.split('/')[-1] if pope else ''
    text.append(f"\n   {emoji('pope')} Pope: ", style=GOLD)
    text.append(f"{pope_name}\n", style="white")

    # Mode
    mode = config.get('mode', '')
    text.append(f"\n   Mode: ", style="dim")
    text.append(f"{mode}\n", style=CYAN)

    if mode == 'simple':
        # Show which provider
        simple = config.get('simple', {})
        for provider_name, provider_config in simple.items():
            if isinstance(provider_config, dict) and provider_config.get('enabled'):
                text.append(f"   Provider: ", style="dim")
                text.append(f"{provider_name}\n", style=CYAN)

    elif mode == 'mixed':
        # Show routing
        text.append("\n   Routing:\n", style="dim")
        routing = config.get('mixed', {}).get('routing', {})
        for model_id, provider in routing.items():
            model_name = model_id.split('/')[-1]
            text.append(f"      {model_name} → {provider}\n", style="dim")

    text.append("\n   Ready to use Synod!\n", style=GREEN)

    panel = Panel(
        text,
        title=f"[{GREEN}]✓ Configuration Summary[/{GREEN}]",
        border_style=GREEN,
    )

    console.print()
    console.print(panel)
    console.print()
