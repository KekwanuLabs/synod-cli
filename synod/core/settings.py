# synod/core/settings.py
import json
import os
import typer
import inquirer
import questionary
from inquirer.themes import Theme
from typing import List, Dict, Any, Tuple, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED, HEAVY
from rich.align import Align

from .openrouter import query_model_list
from .config import get_api_key, CONFIG_FILE, CONFIG_DIR
from .theme import PRIMARY, CYAN, GOLD, GREEN, emoji
from . import onboarding

console = Console()

# Custom Synod theme for inquirer - vibrant and stunning!
class SynodTheme(Theme):
    def __init__(self):
        super().__init__()
        # Stunning color scheme - bright and vibrant!
        self.Question.mark_color = '\x1b[1;38;5;141m'  # BRIGHT Purple/Primary
        self.Question.brackets_color = '\x1b[1;38;5;141m'  # BRIGHT Purple
        self.Question.default_color = '\x1b[1;38;5;75m'  # BRIGHT Cyan

        # Checkbox: Selected items in BRIGHT purple, unselected dimmer
        self.Checkbox.selection_color = '\x1b[1;38;5;213m'  # BRIGHT Magenta/Purple (cursor)
        self.Checkbox.selection_icon = '❯'
        self.Checkbox.selected_icon = '◉'  # Filled circle for checked
        self.Checkbox.unselected_icon = '◯'  # Empty circle for unchecked
        self.Checkbox.selected_color = '\x1b[1;38;5;141m'  # BRIGHT Purple for checked items
        self.Checkbox.unselected_color = '\x1b[38;5;245m'  # Dimmer gray for unchecked

        # List: Bright purple cursor
        self.List.selection_color = '\x1b[1;38;5;213m'  # BRIGHT Magenta/Purple
        self.List.selection_cursor = '❯'
        self.List.unselected_color = '\x1b[38;5;245m'  # Dimmer gray

DEFAULT_BISHOP_MODELS = [
    "openai/gpt-4o",                 # GPT-4o - Best all-around, widely available in Azure
    "openai/gpt-4-turbo",            # GPT-4 Turbo - Fast and capable (can map to gpt-4.5-preview in Azure)
    "x-ai/grok-4.1-fast:free",       # xAI Grok 4.1 Fast (free on OpenRouter)
    "anthropic/claude-sonnet-4.5",   # Claude Sonnet 4.5 - Best reasoning (if available)
]
DEFAULT_POPE_MODEL = "openai/gpt-4o"  # GPT-4o for synthesis (widely available in Azure and OpenRouter)

class SynodSettings:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SynodSettings, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        self.bishop_models: List[str] = DEFAULT_BISHOP_MODELS
        self.pope_model: str = DEFAULT_POPE_MODEL
        self.api_key: str | None = None

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config_data = json.load(f)
                    # Support both old "cardinal_models" and new "bishop_models" keys for backwards compatibility
                    self.bishop_models = config_data.get("bishop_models", config_data.get("cardinal_models", DEFAULT_BISHOP_MODELS))
                    self.pope_model = config_data.get("pope_model", DEFAULT_POPE_MODEL)
                    self.api_key = config_data.get("api_key")
            except json.JSONDecodeError:
                console.print(f"[bold red]Warning:[/bold red] Invalid JSON in {CONFIG_FILE}. Using default settings.")
        else:
            # If config doesn't exist, check if we have an API key in config.py logic (e.g. env var)
            self.api_key = get_api_key()
            console.print(f"[italic dim]No Synod configuration found. Using defaults.[/italic dim]")

    def save_config(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        config_data = {
            "bishop_models": self.bishop_models,
            "pope_model": self.pope_model,
        }
        if self.api_key:
            config_data["api_key"] = self.api_key

        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
        console.print(f"[bold green]Configuration saved to {CONFIG_FILE}[/bold green]")

    async def run_onboarding(self) -> bool:
        """Complete onboarding flow for first-time users."""
        # Step 1: Welcome screen
        onboarding.show_welcome_screen()
        console.input("[dim]Press Enter to continue...[/dim] ")

        # Step 2: OpenRouter instructions
        onboarding.show_openrouter_instructions()
        console.input("[dim]Press Enter when you have your API key ready...[/dim] ")

        # Step 3: Get API key
        api_key = onboarding.get_api_key_input()
        if not api_key:
            console.print("[error]Setup cancelled.[/error]")
            return False

        # Save API key immediately so we can fetch models
        self.api_key = api_key
        self.save_config()

        # Step 4: Explain council structure
        onboarding.show_model_selection_intro()
        console.input("[dim]Press Enter to select your bishops...[/dim] ")

        # Step 5: Fetch available models
        console.print(f"\n[{CYAN}]Fetching available models from OpenRouter...[/{CYAN}]\n")
        available_models = await query_model_list()

        if not available_models:
            console.print("[error]Could not fetch models. Please check your API key and try again.[/error]")
            return False

        console.print(f"[success]✓ Found {len(available_models)} models[/success]\n")

        # Step 6: Show recommendations
        onboarding.show_bishop_recommendations()

        # Step 7: Select bishops (simplified UI using console.input)
        selected_bishops = await self._select_bishops_simple(available_models)
        if not selected_bishops:
            return False

        # Step 8: Select pope from bishops
        selected_pope = self._select_pope_simple(selected_bishops)
        if not selected_pope:
            return False

        # Save configuration
        self.bishop_models = selected_bishops
        self.pope_model = selected_pope
        onboarding.save_onboarding_config(api_key, selected_bishops, selected_pope)

        # Step 9: Completion screen
        onboarding.show_completion_screen(selected_bishops, selected_pope)

        return True

    async def _select_bishops_simple(self, available_models: List[Dict]) -> Optional[List[str]]:
        """Simplified bishop selection with curated top models from major providers."""

        # Stunning header panel with bright continuous border
        header = Text()
        header.append(f"{emoji('bishop')} ", style=f"bold {CYAN}")
        header.append("Select Your Bishops", style=f"bold {PRIMARY}")
        header.append(f" {emoji('bishop')}", style=f"bold {CYAN}")

        subtitle = Text()
        subtitle.append("\nThese AI models will debate your code from different perspectives\n", style="dim")
        subtitle.append("Core models are pre-selected for optimal results\n", style=f"bold {GREEN}")

        header.append("\n")
        header.append(subtitle)

        panel = Panel(
            Align.center(header),
            border_style=f"bold {PRIMARY}",
            box=HEAVY,
            padding=(1, 2),
        )
        console.print(panel)
        console.print()

        # Our 7 curated models with display info
        # Format: (model_id, display_name, description, is_core, is_free)
        # Model IDs must match exactly what OpenRouter uses
        CURATED_MODELS = [
            ("anthropic/claude-sonnet-4.5", "Claude Sonnet 4.5", "Best reasoning", True, False),
            ("openai/gpt-5.1-chat", "GPT 5.1 Chat", "Latest from OpenAI", True, False),
            ("x-ai/grok-4.1-fast:free", "Grok 4.1 Fast", "xAI - FREE!", True, True),
            ("google/gemini-3-pro-preview", "Gemini 3 Pro", "Google multimodal", True, False),
            ("deepseek/deepseek-chat-v3.1", "DeepSeek V3.1", "Algorithms expert", True, False),
            ("z-ai/glm-4.6", "GLM 4.6", "Zhipu AI", False, False),
            ("anthropic/claude-opus-4.5", "Claude Opus 4.5", "Recommended Pope", False, False),
        ]

        # Build model lookup from available models for context info
        available_lookup = {m['id']: m for m in available_models}

        top_models = []
        for model_id, display_name, desc, is_core, is_free in CURATED_MODELS:
            # Check if model is available on OpenRouter
            if model_id in available_lookup:
                model_info = available_lookup[model_id]
                top_models.append({
                    'id': model_id,
                    'display_name': display_name,
                    'description': desc,
                    'is_core': is_core,
                    'is_free': is_free,
                    'context_length': model_info.get('context_length', 'N/A'),
                })
            else:
                # Model not in OpenRouter list - still add it with default info
                top_models.append({
                    'id': model_id,
                    'display_name': display_name,
                    'description': desc,
                    'is_core': is_core,
                    'is_free': is_free,
                    'context_length': 'N/A',
                })

        # Prepare checkbox choices with detailed labels
        choices = []
        default_selected = []

        # Stunning instructions with vibrant colors
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

        for i, model in enumerate(top_models):
            display_name = model['display_name']
            desc = model['description']
            is_core = model['is_core']

            # Build display label with emojis
            if i == 0:  # Claude Sonnet (required)
                label = f"⭐ {display_name:<24} ({desc})"
            elif is_core:  # Core models
                label = f"✨ {display_name:<24} ({desc})"
            else:  # Optional
                label = f"   {display_name:<24} ({desc})"

            choices.append((label, model['id']))

            # Pre-select core models
            if is_core:
                default_selected.append((label, model['id']))

        # Validation function to ensure Claude is always selected
        def validate_selection(answers, current):
            if not current:
                return "Please select at least 3 models"
            if len(current) < 3:
                return "Please select at least 3 models"
            # Check if Claude (first model) is selected
            claude_choice = choices[0]
            if claude_choice not in current:
                return "Claude is required for best results"
            return True

        # Show interactive checkbox with custom theme
        questions = [
            inquirer.Checkbox(
                'bishops',
                message="Select your Bishops",
                choices=choices,
                default=default_selected,
                validate=validate_selection,
            ),
        ]

        answers = inquirer.prompt(questions, theme=SynodTheme())

        if not answers or not answers['bishops']:
            console.print("[error]Selection cancelled.[/error]")
            return None

        selected = answers['bishops']

        # Beautiful success panel
        success_text = Text()
        success_text.append("✓ ", style=f"bold {GREEN}")
        success_text.append(f"Selected {len(selected)} Bishops", style=f"bold {GREEN}")
        success_text.append("\n\n", style="")

        for model_id in selected:
            model_name = model_id.split('/')[-1] if '/' in model_id else model_id
            if 'claude' in model_id.lower():
                success_text.append("⭐ ", style=GOLD)
            elif model_id in [m['id'] for m in top_models[:core_count]]:
                success_text.append("✨ ", style=CYAN)
            else:
                success_text.append("  ", style="")
            success_text.append(f"{model_name}\n", style="white")

        panel = Panel(
            Align.center(success_text),
            title="Council Assembled",
            border_style=GREEN,
            box=ROUNDED,
        )
        console.print()
        console.print(panel)
        console.print()

        return selected

    def _select_pope_simple(self, bishops: List[str]) -> Optional[str]:
        """Simplified pope selection using arrow keys."""

        # Stunning header panel with bright continuous border
        header = Text()
        header.append(f"{emoji('pope')} ", style=f"bold {GOLD}")
        header.append("Select Your Pope", style=f"bold {GOLD}")
        header.append(f" {emoji('pope')}", style=f"bold {GOLD}")

        subtitle = Text()
        subtitle.append("\nThe Pope synthesizes the final solution from all bishop debates\n", style="dim")
        subtitle.append("Claude 4.5 is recommended for best synthesis\n", style=f"bold {CYAN}")

        header.append("\n")
        header.append(subtitle)

        panel = Panel(
            Align.center(header),
            border_style=f"bold {GOLD}",
            box=HEAVY,
            padding=(1, 2),
        )
        console.print(panel)
        console.print()

        # Find Claude for default
        claude_model = None
        for bishop in bishops:
            if 'claude' in bishop.lower():
                claude_model = bishop
                break

        # Prepare choices with beautiful formatting
        choices = []
        for bishop in bishops:
            model_name = bishop.split('/')[-1] if '/' in bishop else bishop
            if bishop == claude_model:
                label = f"⭐ {model_name:<40} 🏆 Recommended"
            else:
                label = f"   {model_name:<40}"
            choices.append((label, bishop))

        # Stunning instructions with vibrant colors
        instructions = Text()
        instructions.append("💡 ", style=f"bold {GOLD}")
        instructions.append("Use ", style="dim")
        instructions.append("↑↓", style=f"bold {CYAN}")
        instructions.append(" to navigate  •  ", style="dim")
        instructions.append("ENTER", style=f"bold {GREEN}")
        instructions.append(" to confirm", style="dim")

        console.print(Align.center(instructions))
        console.print()

        # Show interactive list with custom theme
        questions = [
            inquirer.List(
                'pope',
                message="Choose your Pope",
                choices=choices,
                default=claude_model if claude_model else bishops[0],
            ),
        ]

        answers = inquirer.prompt(questions, theme=SynodTheme())

        if not answers or not answers['pope']:
            console.print("[error]Selection cancelled.[/error]")
            return None

        selected_pope = answers['pope']
        pope_name = selected_pope.split('/')[-1] if '/' in selected_pope else selected_pope

        # Beautiful success panel
        success_text = Text()
        success_text.append("👑 ", style=GOLD)
        success_text.append(f"{pope_name}", style=f"bold {GOLD}")
        success_text.append("\n\nThe Pope will weave the final solution", style="dim")

        panel = Panel(
            Align.center(success_text),
            title="Pope Selected",
            border_style=GOLD,
            box=ROUNDED,
        )
        console.print()
        console.print(panel)
        console.print()

        return selected_pope

    async def configure_models_interactively(self):
        console.print(Panel(Text("Synod Configuration", style="bold yellow"), title="Setup", border_style="yellow", box=ROUNDED))
        console.print("Let's configure your Synod Bishops and Pope.")

        # 1. API Key Setup
        current_key = get_api_key()
        if not current_key:
            console.print("\n[bold blue]OpenRouter API Key Required[/bold blue]")
            console.print("To fetch available models and run the council, you need an API key from [link=https://openrouter.ai/keys]OpenRouter.ai[/link].")
            new_key = await questionary.password("Enter your OpenRouter API Key:").ask_async()
            if new_key:
                self.api_key = new_key.strip()
                # We need to save this immediately so query_model_list can work
                self.save_config() 
            else:
                console.print("[bold red]API Key is required to proceed.[/bold red]")
                return False
        else:
            console.print(f"\n[green]API Key found.[/green] (Ends with ...{current_key[-4:]})")
            update_key = await questionary.confirm("Do you want to update your API key?", default=False).ask_async()
            if update_key:
                new_key = await questionary.password("Enter your new OpenRouter API Key:").ask_async()
                if new_key:
                    self.api_key = new_key.strip()
                    self.save_config()

        # 2. Fetch Models
        console.print("\n[bold blue]Fetching available models from OpenRouter...[/bold blue]")
        available_models = await query_model_list()
        
        if not available_models:
            console.print(Panel(
                Text("Could not fetch models from OpenRouter. Please check your API key and internet connection.", style="bold red"),
                title="Model Fetch Failed", border_style="red"
            ))
            return False
        
        # Specific models we support - exact model IDs from OpenRouter
        SUPPORTED_MODELS = [
            "anthropic/claude-opus-4.5",
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5.1-chat",
            "google/gemini-3-pro-preview",
            "x-ai/grok-4.1-fast:free",
            "deepseek/deepseek-chat-v3.1",
            "z-ai/glm-4.6",
        ]

        # Prepare choices for Questionary - only show supported models
        model_choices = []
        model_map = {} # Map display string back to model ID
        for m in available_models:
            model_id = m['id']
            # Only include specific supported models
            if model_id in SUPPORTED_MODELS:
                display_name = f"{model_id} (pricing: ${m.get('pricing',{}).get('prompt', 'N/A')}/1K, context: {m.get('context', 'N/A')}K)"
                model_choices.append(display_name)
                model_map[display_name] = model_id
        
        if not model_choices:
            console.print(Panel(
                Text("No models found from OpenRouter. Try again later or manually update config.", style="bold red"),
                title="No Models", border_style="red"
            ))
            return False

        # 3. Select Bishops (Checkbox)
        console.print("\n[bold]Select your Bishops (at least 3, ideally 3-5 for debate):[/bold]")
        console.print("[italic dim]Use arrow keys to move, space to select, enter to confirm.[/italic dim]")

        # Don't pre-select defaults - let users choose from scratch
        # Model names change frequently on OpenRouter, causing matching issues
        selected_bishop_displays = await questionary.checkbox(
            "Select Bishops:",
            choices=model_choices,
            validate=lambda choices: True if len(choices) >= 3 else "Please select at least 3 Bishop models."
        ).ask_async()

        if not selected_bishop_displays:
             console.print("[bold red]Selection cancelled or invalid.[/bold red]")
             return False

        self.bishop_models = [model_map[display] for display in selected_bishop_displays]

        console.print(f"\n[bold]Selected Bishops:[/bold] {', '.join(self.bishop_models)}")

        # 4. Select Pope (Select from Bishops)
        console.print("\n[bold]Select your Pope from the Bishops (best reasoning/synthesis model recommended):[/bold]")
        console.print("[italic dim]The Pope is the Bishop of Rome, chosen from among the Bishops to preside and synthesize the final solution.[/italic dim]")

        # Build choices from selected bishops
        pope_choices = [model_map[display] for display in selected_bishop_displays]
        pope_display_map = {model_id: display for display, model_id in model_map.items() if model_id in pope_choices}
        pope_choice_list = [pope_display_map[model_id] for model_id in pope_choices]

        # Try to set default pointer for Pope if available (Claude Sonnet 4.5)
        default_pope_choice = None
        for display in pope_choice_list:
            if "claude" in display.lower() and "sonnet" in display.lower():
                default_pope_choice = display
                break

        if not default_pope_choice and pope_choice_list:
             default_pope_choice = pope_choice_list[0]

        selected_pope_display = await questionary.select(
            "Select Pope:",
            choices=pope_choice_list,
            default=default_pope_choice
        ).ask_async()
        
        if not selected_pope_display:
             console.print("[bold red]Selection cancelled.[/bold red]")
             return False

        self.pope_model = model_map[selected_pope_display]
        
        console.print(f"\n[bold]Selected Pope Model:[/bold] {self.pope_model}")

        self.save_config()
        console.print(Panel(Text("Synod configuration complete!", style="bold green"), title="Success", border_style="green", box=ROUNDED))
        return True

# Initialize settings
settings = SynodSettings()
BISHOP_MODELS = settings.bishop_models
POPE_MODEL = settings.pope_model

# Helper for initial setup check (used by CLI)
async def ensure_configured():
    """
    Ensure Synod is configured, using template or interactive onboarding.

    Priority:
    1. Check for template file (.synod.template.yaml)
    2. If template exists and filled → validate and apply
    3. If template invalid → show errors, offer interactive setup
    4. If no template → run interactive onboarding
    """
    settings_instance = SynodSettings() # Ensure latest config is loaded
    api_key = get_api_key() # Check globally accessible key

    # Import template module
    try:
        from . import template
    except ImportError:
        console.print("[warning]Warning: Template module not available. Install PyYAML: pip install pyyaml[/warning]")
        template = None

    # Check if user is already onboarded
    is_already_onboarded = onboarding.is_onboarded()

    # Priority 1: Check for template file
    if template and template.is_template_filled():
        console.print(f"\n[{CYAN}]📄 Found configuration template[/{CYAN}]")

        # Try to apply template
        success = template.apply_template_config()

        if success:
            # Template applied successfully
            settings_instance._load_config()
            return settings_instance
        else:
            # Template validation failed
            console.print(f"\n[{GOLD}]Would you like to use interactive setup instead?[/{GOLD}]")
            response = console.input("[dim]Continue with interactive setup? [Y/n]:[/dim] ")

            if response.lower() in ['', 'y', 'yes']:
                # Fall through to interactive onboarding
                pass
            else:
                console.print("[error]Setup cancelled. Fix template errors and try again.[/error]")
                raise typer.Exit(code=1)

    # Priority 2: Run interactive onboarding if needed
    if not is_already_onboarded:
        # First-time user - run beautiful onboarding flow
        try:
            onboarding.run_interactive_setup()
            # Reload settings after onboarding
            settings_instance._load_config()
        except Exception as e:
            console.print(f"[error]Setup failed: {e}[/error]")
            console.print("[error]Run 'synod config' to try again.[/error]")
            raise typer.Exit(code=1)

    elif not settings_instance.bishop_models or not settings_instance.pope_model or not api_key:
        # Config exists but incomplete - run quick config
        console.print(Panel(
            Text("Synod configuration incomplete. Running setup...", style="bold yellow"),
            title="Setup Required",
            border_style="yellow"
        ))

        success = await settings_instance.configure_models_interactively()
        if not success:
            console.print("[error]Setup failed. Exiting.[/error]")
            raise typer.Exit(code=1)

        # Reload settings after config
        settings_instance._load_config()

    return settings_instance