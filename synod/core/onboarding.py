"""Simplified onboarding experience with smart per-model provider routing.

This module provides a streamlined setup that:
- Lets users select models they want
- Automatically determines required providers
- Collects credentials once per provider (not per model)
- Routes each model to the optimal provider automatically
"""

from typing import List, Optional, Dict, Set
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align
from rich.console import Console
# NOTE: inquirer imported locally in functions to avoid terminal init before logo animation

from .display import console, SYNOD_LOGO, animate_logo
from .theme import PRIMARY, SECONDARY, CYAN, GOLD, GREEN, emoji
from .model_registry import (
    get_required_providers,
    get_all_potential_providers,
    suggest_optimal_provider,
    get_available_providers,
    is_free_tier,
    get_provider_display_name,
    ModelProvider,
)
from .config import CONFIG_FILE, CONFIG_DIR
import os
import json
import getpass


# Custom theme for inquirer (class defined here, but inquirer imported locally)
def _get_synod_theme():
    """Get SynodTheme class - imports inquirer locally to avoid early terminal init."""
    import inquirer
    from inquirer.themes import Theme

    class SynodTheme(Theme):
        def __init__(self):
            super().__init__()
            self.Question.mark_color = '\x1b[1;38;5;141m'
            self.Question.brackets_color = '\x1b[1;38;5;141m'
            self.Question.default_color = '\x1b[1;38;5;75m'
            self.Checkbox.selection_color = '\x1b[1;38;5;213m'
            self.Checkbox.selection_icon = '❯'
            self.Checkbox.selected_icon = '◉'
            self.Checkbox.unselected_icon = '◯'
            self.Checkbox.selected_color = '\x1b[1;38;5;141m'
            self.Checkbox.unselected_color = '\x1b[38;5;245m'
            self.List.selection_color = '\x1b[1;38;5;213m'
            self.List.selection_cursor = '❯'
            self.List.unselected_color = '\x1b[38;5;245m'

    return SynodTheme()


def show_welcome() -> None:
    """Display welcome screen with animated logo."""
    # Animate the logo
    animate_logo()

    # Show welcome message below the animated logo
    console.print()

    welcome = Text()
    welcome.append("Welcome to ", style="dim")
    welcome.append("Synod", style=f"bold {PRIMARY}")
    welcome.append(" - Elite Models Debate. You Get Their Collective Best.\n\n", style="dim")
    welcome.append("Let's get you set up in 3 quick steps", style=CYAN)

    panel = Panel(
        Align.center(welcome),
        border_style=PRIMARY,
        padding=(1, 2),
    )

    console.print(panel)
    console.print()


def show_model_selection_intro() -> None:
    """Explain the council structure."""
    explanation = Text()

    explanation.append(f"\n{emoji('council')}  ", style=PRIMARY)
    explanation.append("How Synod Works\n\n", style=f"bold {PRIMARY}")

    explanation.append("   Synod harnesses ", style="dim")
    explanation.append("collective intelligence", style=f"bold {GOLD}")
    explanation.append(" from SOTA models.\n", style="dim")
    explanation.append("   Models act as ", style="dim")
    explanation.append("Bishops", style=f"bold {CYAN}")
    explanation.append(" who rigorously debate proposals, while a\n", style="dim")
    explanation.append("   Chief Bishop (", style="dim")
    explanation.append("Pope", style=f"bold {SECONDARY}")
    explanation.append(") arbitrates and synthesizes the best parts.\n\n", style="dim")

    explanation.append("   ", style="dim")
    explanation.append("1. ", style=f"bold {CYAN}")
    explanation.append("Bishops propose ", style=CYAN)
    explanation.append("solutions independently\n", style="dim")

    explanation.append("   ", style="dim")
    explanation.append("2. ", style=f"bold {CYAN}")
    explanation.append("They critique ", style=CYAN)
    explanation.append("each other's proposals\n", style="dim")

    explanation.append("   ", style="dim")
    explanation.append("3. ", style=f"bold {SECONDARY}")
    explanation.append("Pope synthesizes ", style=SECONDARY)
    explanation.append("the best parts into one solution\n\n", style="dim")

    explanation.append("   💡  ", style=GOLD)
    explanation.append("Select 3-5 diverse bishops (i.e. SOTA models) for the best results\n\n", style="dim")

    panel = Panel(
        explanation,
        title=f"[{CYAN}]Step 1: Select Your Bishops[/{CYAN}]",
        border_style=CYAN,
    )

    console.print(panel)
    console.print()


def select_models() -> Optional[List[str]]:
    """Let user select models via checkbox."""
    import inquirer  # Local import to avoid early terminal init

    # The 6 SOTA Bishop Models - these are the ONLY models we use
    # Format: (display_label, model_id, default_selected)
    available_models = [
        ("⭐ Claude Opus 4.5         (Recommended Pope)", "anthropic/claude-opus-4.5", True),
        ("✨ Claude Sonnet 4.5       (Fast, high-quality)", "anthropic/claude-sonnet-4.5", False),
        ("✨ GPT 5.1 Chat            (Latest from OpenAI)", "openai/gpt-5.1-chat", True),
        ("✨ Grok 4.1 Fast (free)    (xAI - FREE!)", "x-ai/grok-4.1-fast:free", True), # Updated Grok model ID
        ("✨ Gemini 3.0              (Google multimodal)", "google/gemini-3-pro-preview", True),
        ("✨ DeepSeek V3.1           (Algorithms expert)", "deepseek/deepseek-chat-v3.1", False),
    ]

    choices = [(label, model_id) for label, model_id, _ in available_models]
    default_selected = [(label, model_id) for label, model_id, selected in available_models if selected]

    # Instructions
    instructions = Text()
    instructions.append("💡 ", style=f"bold {GOLD}")
    instructions.append("Use ", style="dim")
    instructions.append("↑↓", style=f"bold {CYAN}")
    instructions.append(" to navigate  •  ", style="dim")
    instructions.append("SPACE", style=f"bold {PRIMARY}")
    instructions.append(" to toggle  •  ", style="dim")
    instructions.append("ENTER", style=f"bold {GREEN}")
    instructions.append(" to confirm", style="dim")

    console.print(Align.center(instructions))
    console.print()

    # Validation
    def validate_selection(answers, current):
        if not current or len(current) < 3:
            return "Please select at least 3 models for best results"

        # Ensure Claude Opus is selected (recommended Pope)
        claude_opus_choice = choices[0]
        if claude_opus_choice not in current:
            return "Claude Opus 4.5 is highly recommended (best Pope model)"

        # Check for duplicate providers
        providers = []
        for choice in current:
             # choice is the model_id string, e.g., "anthropic/claude-opus-4.5"
             if "/" in choice:
                 provider = choice.split("/")[0]
                 if provider in providers:
                     return f"You can only select one model from {provider.title()}."
                 providers.append(provider)

        return True

    questions = [
        inquirer.Checkbox(
            'models',
            message="Select your Bishops",
            choices=choices,
            default=default_selected,
            validate=validate_selection,
        ),
    ]

    answers = inquirer.prompt(questions, theme=_get_synod_theme())

    if not answers or not answers['models']:
        console.print("[error]Selection cancelled.[/error]")
        return None

    return answers['models']


def analyze_provider_needs(model_ids: List[str]) -> Dict:
    """
    Analyze which providers are needed and create routing plan.

    Returns dict with:
    - required_providers: Set of providers needed
    - can_use_openrouter: bool (if OpenRouter can handle everything)
    - model_routing: Dict of model -> suggested provider
    """
    required = get_required_providers(model_ids)
    all_potential = get_all_potential_providers(model_ids)

    # Check if OpenRouter can serve everything
    can_use_openrouter = all(
        ModelProvider.OPENROUTER in get_available_providers(model_id)
        for model_id in model_ids
    )

    # Create initial routing plan (will be optimized after credentials collected)
    model_routing = {}
    for model_id in model_ids:
        providers = get_available_providers(model_id)
        # Default to OpenRouter if available, otherwise first provider
        if ModelProvider.OPENROUTER in providers:
            model_routing[model_id] = ModelProvider.OPENROUTER
        else:
            model_routing[model_id] = next(iter(providers))

    return {
        'required_providers': required,
        'all_potential_providers': all_potential,
        'can_use_openrouter': can_use_openrouter,
        'model_routing': model_routing,
        'all_models': model_ids,
    }


def show_provider_analysis(analysis: Dict) -> str:
    """
    Show provider analysis and let user choose approach.

    Returns: "simple" or "custom"
    """
    text = Text()

    text.append(f"\n{emoji('info')} ", style=PRIMARY)
    text.append("Provider Analysis\n\n", style=f"bold {PRIMARY}")

    if analysis['can_use_openrouter']:
        # Simple path available
        text.append("   ✅ ", style=GREEN)
        text.append("All your models are available on OpenRouter!\n\n", style=GREEN)

        text.append("   🎯 ", style=CYAN)
        text.append("Recommended: ", style=f"bold {CYAN}")
        text.append("Use OpenRouter for everything\n", style="dim")
        text.append("      • One API key\n", style="dim")
        text.append("      • 2-minute setup\n", style="dim")
        text.append("      • Unified billing\n\n", style="dim")

        text.append("   💰 ", style=GOLD)
        text.append("Alternative: ", style=f"bold {GOLD}")
        text.append("Use your cloud credits\n", style="dim")
        text.append("      • Azure, AWS, or Google\n", style="dim")
        text.append("      • Requires multiple credentials\n", style="dim")
        text.append("      • May save costs\n\n", style="dim")

    else:
        # Some models need specific providers
        text.append("   ⚠️  ", style=GOLD)
        text.append("Your models require multiple providers\n\n", style=GOLD)

        # Show which models need what
        for model_id in analysis['all_models']:
            providers = get_available_providers(model_id)
            model_name = model_id.split('/')[-1]

            if len(providers) == 1:
                provider = next(iter(providers))
                text.append(f"      • {model_name}: ", style="dim")
                text.append(get_provider_display_name(provider), style=CYAN)
                text.append(" only\n", style="dim")

        text.append("\n   We'll collect credentials for each provider you need\n\n", style="dim")

    panel = Panel(
        text,
        title=f"[{PRIMARY}]Step 2: Provider Setup[/{PRIMARY}]",
        border_style=PRIMARY,
    )

    console.print(panel)
    console.print()

    if analysis['can_use_openrouter']:
        # Give user choice
        import inquirer  # Local import to avoid early terminal init

        questions = [
            inquirer.List(
                'approach',
                message="Choose your setup",
                choices=[
                    ("🚀 OpenRouter for all (Recommended)", "simple"),
                    ("⚙️  Use my cloud credits (Custom)", "custom"),
                ],
            ),
        ]

        answers = inquirer.prompt(questions, theme=_get_synod_theme())
        return answers['approach'] if answers else "simple"
    else:
        # No choice, need custom
        return "custom"


def collect_provider_credentials(providers: Set[ModelProvider]) -> Dict[ModelProvider, Dict]:
    """
    Collect credentials for each required provider.

    Returns dict mapping provider to credentials.
    """
    credentials = {}

    console.print(f"\n[{CYAN}]Let's collect your credentials[/{CYAN}]\n")

    for provider in providers:
        provider_name = get_provider_display_name(provider)

        console.print(f"[{PRIMARY}]▸ {provider_name}[/{PRIMARY}]")

        creds = {}

        if provider == ModelProvider.OPENROUTER:
            console.print("   Get your API key at: https://openrouter.ai/keys")
            api_key = getpass.getpass("   API Key: ")
            if api_key:
                creds['api_key'] = api_key.strip()

        elif provider == ModelProvider.AZURE_FOUNDRY:
            console.print("   From Azure AI Foundry project settings:")
            endpoint = input("   Endpoint URL: ")
            api_key = getpass.getpass("   API Key: ")
            if endpoint and api_key:
                creds['endpoint'] = endpoint.strip()
                creds['api_key'] = api_key.strip()

        elif provider == ModelProvider.AZURE_OPENAI:
            console.print("   From Azure OpenAI resource:")
            endpoint = input("   Endpoint URL: ")
            api_key = getpass.getpass("   API Key: ")
            if endpoint and api_key:
                creds['endpoint'] = endpoint.strip()
                creds['api_key'] = api_key.strip()

        elif provider == ModelProvider.GOOGLE_VERTEX:
            console.print("   From Google Cloud Console:")
            project = input("   Project ID: ")
            region = input("   Region (default: us-central1): ") or "us-central1"
            if project:
                creds['project_id'] = project.strip()
                creds['region'] = region.strip()

        elif provider == ModelProvider.ANTHROPIC:
            console.print("   Get your API key at: https://console.anthropic.com/settings/keys")
            api_key = getpass.getpass("   API Key: ")
            if api_key:
                creds['api_key'] = api_key.strip()

        elif provider == ModelProvider.OPENAI:
            console.print("   Get your API key at: https://platform.openai.com/api-keys")
            api_key = getpass.getpass("   API Key: ")
            if api_key:
                creds['api_key'] = api_key.strip()

        if creds:
            credentials[provider] = creds
            console.print(f"   [success]✓ Configured[/success]\n")
        else:
            console.print(f"   [warning]⚠ Skipped[/warning]\n")

    return credentials


def optimize_routing(model_ids: List[str], credentials: Dict[ModelProvider, Dict]) -> Dict[str, ModelProvider]:
    """
    Optimize model routing based on configured providers.

    Priority:
    1. Use configured providers (reuse credentials)
    2. Prefer OpenRouter if configured
    3. Use first available
    """
    configured = set(credentials.keys())
    routing = {}

    for model_id in model_ids:
        provider = suggest_optimal_provider(model_id, configured)
        routing[model_id] = provider

    return routing


def show_routing_summary(routing: Dict[str, ModelProvider], credentials: Dict) -> None:
    """Display final routing configuration."""
    text = Text()

    text.append(f"\n{emoji('success')} ", style=GREEN)
    text.append("Setup Complete!\n\n", style=f"bold {GREEN}")

    text.append("   Your Configuration:\n\n", style="dim")

    for model_id, provider in routing.items():
        model_name = model_id.split('/')[-1]
        provider_name = get_provider_display_name(provider)

        # Icon based on provider
        if is_free_tier(model_id):
            icon = "🆓"
        elif provider == ModelProvider.OPENROUTER:
            icon = "🌐"
        elif "azure" in provider.value:
            icon = "☁️"
        elif "google" in provider.value:
            icon = "🔵"
        else:
            icon = "⚡"

        text.append(f"   {icon} ", style="dim")
        text.append(f"{model_name:<30}", style="white")
        text.append(" → ", style="dim")
        text.append(f"{provider_name}\n", style=CYAN)

    text.append("\n   All models will route automatically!\n\n", style="dim")

    panel = Panel(
        text,
        title=f"[{GREEN}]Configuration Summary[/{GREEN}]",
        border_style=GREEN,
    )

    console.print(panel)
    console.print()


def select_pope(bishops: List[str]) -> Optional[str]:
    """Select Pope from bishops."""
    import inquirer  # Local import to avoid early terminal init

    console.print(f"\n[{GOLD}]Step 3: Select Your Pope[/{GOLD}]\n")
    console.print("[dim]The Pope synthesizes the final solution from all bishop debates[/dim]\n")

    # Find Claude for default
    claude_model = None
    for bishop in bishops:
        if 'claude' in bishop.lower():
            claude_model = bishop
            break

    choices = []
    for bishop in bishops:
        model_name = bishop.split('/')[-1]
        if bishop == claude_model:
            label = f"⭐ {model_name:<40} 🏆 Recommended"
        else:
            label = f"   {model_name:<40}"
        choices.append((label, bishop))

    questions = [
        inquirer.List(
            'pope',
            message="Choose your Pope",
            choices=choices,
            default=claude_model if claude_model else bishops[0],
        ),
    ]

    answers = inquirer.prompt(questions, theme=_get_synod_theme())

    if not answers or not answers['pope']:
        return None

    return answers['pope']


def save_configuration(
    bishops: List[str],
    pope: str,
    routing: Dict[str, ModelProvider],
    credentials: Dict[ModelProvider, Dict]
) -> None:
    """Save configuration to files."""
    os.makedirs(CONFIG_DIR, exist_ok=True)

    # Save to ~/.synod/config.json
    config_data = {
        "bishop_models": bishops,
        "pope_model": pope,
        "onboarded": True,
        "version": "2.0.0",
        "routing_mode": "per_model",
    }

    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=2)

    # Save credentials to .env in project root
    env_path = os.path.join(os.getcwd(), '.env')

    with open(env_path, 'w') as f:
        f.write("# Synod Provider Configuration\n")
        f.write("# Generated by Synod onboarding\n\n")

        # Write credentials for each provider
        for provider, creds in credentials.items():
            provider_upper = provider.value.upper().replace('-', '_')
            f.write(f"# {get_provider_display_name(provider)}\n")

            for key, value in creds.items():
                env_key = f"{provider_upper}_{key.upper()}"
                f.write(f"{env_key}={value}\n")
            f.write("\n")

        # Write model routing
        f.write("# Model Routing (automatic)\n")
        for model_id, provider in routing.items():
            model_key = model_id.replace('/', '_').replace('-', '_').replace('.', '_').upper()
            f.write(f"{model_key}_PROVIDER={provider.value}\n")

    console.print(f"[success]✓ Configuration saved to {env_path}[/success]\n")


def configure_model_routing(models: List[str], potential_providers: Set[ModelProvider]) -> Dict[str, ModelProvider]:
    """
    Let user configure routing for each model interactively.
    Used in 'Custom' setup mode.
    """
    import inquirer  # Local import
    routing = {}

    console.print(f"\n[{CYAN}]Configure Model Routing[/{CYAN}]")
    console.print("[dim]Select which provider to use for each model.[/dim]\n")

    for model_id in models:
        # Get providers available for this model
        available = get_available_providers(model_id)
        model_name = model_id.split('/')[-1]

        # If only one provider is available, assign it automatically
        if len(available) == 1:
            provider = next(iter(available))
            routing[model_id] = provider
            continue

        # If multiple providers, ask user
        choices = []
        for p in available:
            name = get_provider_display_name(p)
            choices.append((name, p))

        # Default to OpenRouter if available, or first option
        default_choice = ModelProvider.OPENROUTER if ModelProvider.OPENROUTER in available else next(iter(available))

        questions = [
            inquirer.List(
                'provider',
                message=f"Provider for {model_name}",
                choices=choices,
                default=default_choice,
            ),
        ]

        answers = inquirer.prompt(questions, theme=_get_synod_theme())
        if answers:
            routing[model_id] = answers['provider']
        else:
            # Fallback if cancelled
            routing[model_id] = default_choice

    return routing


def run_onboarding_flow() -> bool:
    """Run simplified onboarding flow."""
    # Step 1: Welcome
    show_welcome()
    console.input("[dim]Press Enter to continue...[/dim] ")

    # Step 2: Select models
    show_model_selection_intro()
    models = select_models()
    if not models:
        return False

    console.print(f"\n[success]✓ Selected {len(models)} models[/success]\n")

    # Step 3: Analyze provider needs
    analysis = analyze_provider_needs(models)
    approach = show_provider_analysis(analysis)

    # Step 4: Configure routing and collect credentials
    routing = {}
    credentials = {}

    if approach == "simple":
        # Just OpenRouter for everything
        credentials = collect_provider_credentials({ModelProvider.OPENROUTER})
        # Auto-route everything to OpenRouter
        for m in models:
            routing[m] = ModelProvider.OPENROUTER

    else:
        # Custom - Configure routing first
        routing = configure_model_routing(models, analysis['all_potential_providers'])

        # Determine which providers we actually need based on routing
        required_providers = set(routing.values())

        # Collect credentials for ONLY the chosen providers
        credentials = collect_provider_credentials(required_providers)

    if not credentials:
        console.print("[error]No credentials provided. Setup cancelled.[/error]")
        return False

    # Step 5: Optimize routing (already done in custom mode, but keeps simple mode consistent)
    # For simple mode, routing is already set. For custom, it's set by user.
    # We just show the summary.
    show_routing_summary(routing, credentials)

    # Step 6: Select Pope
    pope = select_pope(models)
    if not pope:
        return False

    pope_name = pope.split('/')[-1]
    console.print(f"\n[success]✓ Pope selected: {pope_name}[/success]\n")

    # Step 7: Save configuration
    save_configuration(models, pope, routing, credentials)

    # Step 8: Success!
    final_text = Text()
    final_text.append("🎉 ", style=GOLD)
    final_text.append("You're all set!\n\n", style=f"bold {GREEN}")
    final_text.append("Try: ", style="dim")
    final_text.append("synod query \"explain this function\" -f myfile.py", style=f"bold {CYAN}")

    panel = Panel(
        Align.center(final_text),
        border_style=GREEN,
    )

    console.print(panel)
    console.print()

    return True


# ============================================================================
# CLI Compatibility Functions
# ============================================================================

def check_config_exists() -> bool:
    """Check if ~/.synod/config.json exists and is valid.

    Returns:
        True if config exists and is valid, False otherwise
    """
    from pathlib import Path

    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        return False

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Validate required fields
        required_fields = ['bishop_models', 'pope_model']
        for field in required_fields:
            if field not in config:
                return False

        # Validate bishops list has at least 3 models
        if not isinstance(config['bishop_models'], list) or len(config['bishop_models']) < 3:
            return False

        # Validate pope is one of the bishops
        if config['pope_model'] not in config['bishop_models']:
            return False

        return True

    except (json.JSONDecodeError, IOError):
        return False


def run_interactive_setup() -> None:
    """Run the full interactive onboarding wizard.

    This is the main entry point called by cli.py for first-time setup.
    """
    success = run_onboarding_flow()

    if not success:
        console.print("[error]Setup was cancelled or failed.[/error]")
        console.print("[dim]Run 'synod config' to try again.[/dim]\n")
        import sys
        sys.exit(1)


def is_onboarded() -> bool:
    """Check if user has completed onboarding.

    This checks for a valid ~/.synod/config.json file with required configuration.

    Returns:
        True if user has completed setup, False otherwise
    """
    return check_config_exists()
