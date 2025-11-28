# synod/cli.py
import typer
from typer import Context
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.box import HEAVY, ROUNDED
from rich.align import Align
import asyncio
import os
from typing import List, Optional
from datetime import datetime

from synod.core.context import read_file_content
from synod.core.council import run_full_council, run_full_council_with_display
from synod.core.settings import ensure_configured, SynodSettings
from synod.core.live_display import LiveDebateDisplay
from synod.core.theme import SYNOD_THEME, SynodStyles, PRIMARY, CYAN, ACCENT, SECONDARY, GOLD, GREEN, format_model_name
from synod.core.display import (
    show_launch_screen,
    show_exit_summary,
    console,  # Use themed console from display
    get_version,
    get_tagline_full,
    TAGLINE_FULL,
)
from synod.core.session import get_current_session, end_session
from synod.core.indexer import quick_index
from synod.core.context_suggestions import suggest_context_files
from synod.core.chat_interface import SynodChatInterface
from synod.core.archives import CouncilArchives
from synod.core.slash_commands import get_command, parse_slash_command, get_all_commands
from synod.core.syntax import render_with_syntax, SyntaxMarkdown

# Version (dynamic from package metadata)
VERSION = get_version()
app = typer.Typer(
    name="synod",
    help=TAGLINE_FULL,
    add_completion=False,
    rich_markup_mode="rich",
)


@app.command()
def version():
    """Show Synod version and tagline."""
    console.print(f"\n[{CYAN}]Synod v{VERSION}[/{CYAN}]")
    console.print(f"[dim]{TAGLINE_FULL}[/dim]\n")

async def _arun_query(prompt: str, file_context: str, skip_config_check: bool = False, archives: Optional[CouncilArchives] = None):
    """Internal async function to run the query logic."""
    # Ensure configured BEFORE starting any spinners
    # (onboarding needs clean console for interactive prompts)
    if not skip_config_check:
        await ensure_configured()

    session = get_current_session()

    # Fun rotating status messages (Synod-themed)
    status_messages = [
        "👨‍⚖️ Synod bishops convening...",
        "⚖️ Weighing competing arguments...",
        "📜 Analyzing from multiple perspectives...",
        "🎭 Adversarial debate in progress...",
        "💭 Deep reasoning and analysis...",
        "🔮 Synthesizing collective insights...",
        "⚡ Lightning fast reasoning...",
        "🧠 Collective intelligence activated...",
        "🎯 Bishops challenging each other...",
        "👑 Pope preparing final synthesis...",
        "💬 Building consensus through debate...",
        "🤝 Models collaborating intensely...",
        "🔍 Examining code from all angles...",
        "⚡ Rapid-fire critiques incoming...",
        "🎪 The great debate continues...",
    ]

    import random
    import asyncio

    message_index = [0]  # Use list to allow mutation in nested function

    async def rotate_messages(live):
        """Rotate through fun status messages with stage info."""
        while True:
            # Create rich display with stage, fun message, and controls
            display = Text()

            # Stage indicator
            display.append("⚡ Stage 1: ", style=f"bold {CYAN}")
            display.append("Bishop Proposals\n", style=CYAN)

            # Fun rotating message
            msg = status_messages[message_index[0] % len(status_messages)]
            display.append("   └─ ", style="dim")
            display.append(msg + "\n\n", style=SynodStyles.HIGHLIGHT)

            # Controls
            display.append("─" * 60 + "\n", style="dim")
            display.append("esc", style=f"bold {GOLD}")
            display.append(": interrupt  │  ", style="dim")
            display.append("ctrl+s", style=f"bold {GOLD}")
            display.append(": summarize  │  ", style="dim")
            display.append("ctrl+b", style=f"bold {GOLD}")
            display.append(": change bishops\n", style="dim")
            display.append("─" * 60 + "\n", style="dim")

            live.update(display)
            message_index[0] += 1
            await asyncio.sleep(2.5)  # Change message every 2.5 seconds

    # Add archives context if provided
    full_context = file_context
    if archives:
        context_str = archives.get_context_for_debate()
        if context_str:
            full_context = f"{context_str}\n\n{file_context}" if file_context else context_str

    try:
        # Get configured models
        settings = SynodSettings()

        # Run council debate with simpler live streaming (no grid)
        stage1_results, dissents, final_solution = await run_full_council_with_display(
            prompt,
            full_context,
            live_display=None  # Pass None to use simpler animated display
        )

        # Record debate
        session.record_debate()

        # Add exchange to archives if provided
        if archives:
            archives.add_exchange(
                query=prompt,
                synthesis=final_solution.get("response", "No solution generated")
            )

        # Display Pope's final solution (THE MAIN OUTPUT!)
        # Include detailed timing info at the top
        timing = final_solution.get("timing", {})
        total_time = timing.get("total", 0)
        stage0_time = timing.get("analysis", 0)
        stage1_time = timing.get("proposals", 0)
        stage2_time = timing.get("critiques", 0)
        stage3_time = timing.get("synthesis", 0)

        # Build the content with timing header
        solution_text = final_solution.get("response", "No solution generated")
        pope_model = final_solution.get("model", "Pope")

        # Format pope model name
        from synod.core.theme import format_model_name
        pope_name = format_model_name(pope_model)

        # Detailed timing line showing all stages
        timing_parts = []
        if stage0_time > 0:
            timing_parts.append(f"Analysis: {stage0_time:.1f}s")
        if stage1_time > 0:
            timing_parts.append(f"Proposals: {stage1_time:.1f}s")
        if stage2_time > 0:
            timing_parts.append(f"Critiques: {stage2_time:.1f}s")
        if stage3_time > 0:
            timing_parts.append(f"Synthesis: {stage3_time:.1f}s")
        timing_parts.append(f"[bold]Total: {total_time:.1f}s[/bold]")

        timing_line = f"[dim]⏱ {' | '.join(timing_parts)}[/dim]"

        console.print()
        # Render markdown for syntax highlighting
        from rich.markdown import Markdown
        from rich.console import Group
        # Text is already imported at module level
        md = Markdown(solution_text, code_theme="monokai")

        # Build final synthesis panel with status, timing and content (all in one)
        content = Group(
            Text(f"✓ {pope_name} complete", style=GREEN),
            Text(""),  # Empty line separator
            Text.from_markup(timing_line),  # Timing info
            Text(""),  # Empty line separator
            md
        )

        console.print(Panel(
            content,
            title=f"[{SECONDARY}]Stage 3: Pope Synthesis[/{SECONDARY}]",
            border_style=SECONDARY,
            padding=(1, 2)
        ))
        console.print()

        # Display archives status if in interactive mode
        if archives:
            console.print()
            archives.display_status(console)
        else:
            # Only show "Debate Complete" in non-interactive mode (single query)
            console.print()
            console.print(
                Panel(
                    Align.center(Text("✨ Debate Complete!", style=f"bold {GREEN}")),
                    border_style=GREEN,
                    padding=(0, 2),
                )
            )

    except Exception as e:
        console.print(
            Panel(
                Text(f"An error occurred during the Synod session: {e}", style="error"),
                title="Synod Error",
                border_style="error",
            )
        )

# Single-query mode disabled - Synod is designed to be interactive only
# Use 'synod' or 'synod interactive' to start a session


@app.command()
def init():
    """
    Create a configuration template file in the current directory.

    This generates a .synod.template.yaml file that you can edit
    to configure Synod without going through interactive prompts.
    """
    try:
        from synod.core import template
        success = template.copy_template_to_project()

        if success:
            console.print()
            console.print(Panel(
                Text("✓ Template created!\n\n"
                     "Edit .synod.template.yaml to configure your models and credentials.\n"
                     "Then run 'synod query' to start using Synod.\n\n"
                     "See docs/QUICKSTART_V2.md for template examples.",
                     style=GREEN),
                title="Template Ready",
                border_style=GREEN,
            ))
    except ImportError:
        console.print("[error]Template module not available. Install PyYAML: pip install pyyaml[/error]")


@app.command()
def config():
    """
    Configure or update your Synod bishops and pope.

    Use this to change your model selection at any time.
    After configuration, launches interactive mode.
    """
    from synod.core.onboarding import check_config_exists, run_interactive_setup
    from synod.core.config import CONFIG_YAML
    from pathlib import Path

    # Check if config exists
    if check_config_exists():
        config_path = Path(CONFIG_YAML)
        console.print(f"\n[{CYAN}]📄 Configuration file already exists:[/{CYAN}]")
        console.print(f"[dim]   {config_path}[/dim]\n")
        console.print(f"[{PRIMARY}]To update your configuration:[/{PRIMARY}]")
        console.print(f"[dim]   1. Edit ~/.synod-cli/config.yaml manually[/dim]")
        console.print(f"[dim]   2. Run: synod config[/dim]")
        console.print(f"[dim]      to regenerate from the wizard[/dim]\n")

        recreate = typer.confirm("Would you like to recreate your configuration from scratch?", default=False)
        if recreate:
            # Remove config and run wizard
            if config_path.exists():
                config_path.unlink()
                console.print(f"[{GREEN}]✓ Removed existing config[/{GREEN}]\n")
            run_interactive_setup()
            # After setup, launch interactive mode
            console.print(f"\n[{CYAN}]✨ Configuration complete! Launching interactive mode...[/{CYAN}]\n")
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:  # No loop is running
                asyncio.run(_interactive_session())
            else:  # Loop is already running, likely from prompt_toolkit
                loop.run_until_complete(_interactive_session())
        else:
            console.print(f"[{GREEN}]Configuration preserved. Use 'synod' to start interactive mode.[/{GREEN}]\n")
    else:
        # No config, run wizard
        run_interactive_setup()
        # After setup, launch interactive mode
        console.print(f"\n[{CYAN}]✨ Configuration complete! Launching interactive mode...[/{CYAN}]\n")
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No loop is running
            asyncio.run(_interactive_session())
        else:  # Loop is already running, likely from prompt_toolkit
            loop.run_until_complete(_interactive_session())

@app.command()
def bishops():
    """
    Update your bishop and pope configuration.

    Alias for 'synod config' - choose your AI models.
    """
    # Just call the config command
    config()

@app.command()
def history(limit: int = typer.Option(10, "--limit", "-n", help="Number of sessions to show")):
    """
    View recent Synod session history.

    Shows your last N sessions with token usage and costs.
    """
    from synod.core.session import get_recent_sessions
    from rich.table import Table

    sessions = get_recent_sessions(limit=limit)

    if not sessions:
        console.print(f"\n[{CYAN}]No session history found.[/{CYAN}]")
        console.print(f"[dim]Sessions are saved in ~/.synod-cli/sessions/[/dim]\n")
        return

    # Create table
    table = Table(title=f"Recent Sessions (Last {limit})", show_header=True, box=HEAVY)
    table.add_column("Date", style=CYAN)
    table.add_column("Time", style="dim")
    table.add_column("Queries", justify="right", style="dim")
    table.add_column("Tokens", justify="right", style="dim")
    table.add_column("Cost", justify="right", style=GOLD)
    table.add_column("Duration", justify="right", style="dim")

    for session in sessions:
        date_str = datetime.fromtimestamp(session.start_time).strftime("%Y-%m-%d")
        time_str = datetime.fromtimestamp(session.start_time).strftime("%H:%M:%S")
        duration = session.get_duration()
        duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"

        table.add_row(
            date_str,
            time_str,
            str(session.debates),
            f"{session.total_tokens:,}",
            f"${session.total_cost:.4f}",
            duration_str
        )

    console.print()
    console.print(table)
    console.print()

@app.command()
def stats():
    """
    Show aggregate statistics across all sessions.

    Displays total usage, costs, and most used models.
    """
    from synod.core.session import get_session_stats

    stats_data = get_session_stats()

    if stats_data["total_sessions"] == 0:
        console.print(f"\n[{CYAN}]No session history found.[/{CYAN}]")
        console.print(f"[dim]Start using Synod to build your stats![/dim]\n")
        return

    # Build stats display
    stats_text = Text()

    stats_text.append("\n📊 Synod Usage Statistics\n\n", style=f"bold {PRIMARY}")

    # Aggregate stats
    stats_text.append("Aggregate Stats\n", style="bold")
    stats_text.append(f"Total Sessions:       {stats_data['total_sessions']}\n", style="dim")
    stats_text.append(f"Total Queries:        {stats_data['total_queries']}\n", style="dim")
    stats_text.append(f"Total Tokens:         {stats_data['total_tokens']:,}\n", style="dim")
    stats_text.append(f"Total Cost:           ${stats_data['total_cost']:.2f}\n\n", style=GOLD)

    # Most used models
    if stats_data["most_used_models"]:
        stats_text.append("Most Used Models\n", style="bold")
        for model_id, count in stats_data["most_used_models"].items():
            model_name = model_id.split('/')[-1] if '/' in model_id else model_id
            if len(model_name) > 30:
                model_name = model_name[:27] + "..."
            stats_text.append(f"  • {model_name:<30} {count} calls\n", style="dim")

    stats_text.append("\n")

    panel = Panel(stats_text, border_style=PRIMARY, box=HEAVY)
    console.print(panel)
    console.print()

@app.command()
def interactive():
    """
    Start an interactive Synod session.

    Type your queries, and type 'exit' to quit.
    """
    asyncio.run(_interactive_session())

# Make 'interactive' the default command
@app.callback(invoke_without_command=True)
def default_command(ctx: typer.Context):
    """
    Synod - Interactive AI coding debates.

    Start chatting with multiple AI models that debate to find the best solution.
    """
    if ctx.invoked_subcommand is None:
        # No command provided, launch interactive mode
        from synod.core.onboarding import is_onboarded

        if not is_onboarded():
            # First time user - run config wizard then launch interactive
            config()
        else:
            # Already configured - launch interactive mode directly
            asyncio.run(_interactive_session())


async def _handle_slash_command(
    command: str,
    args: str,
    session,
    archives,
    settings
) -> bool:
    """Handle a slash command.

    Args:
        command: Command name (without /)
        args: Arguments passed to the command
        session: Current session
        archives: Council archives
        settings: Synod settings

    Returns:
        True if the session should exit, False to continue
    """
    from synod.core.session import display_session_summary
    from rich.table import Table

    if command in ['exit', 'quit', 'q']:
        # Exit command
        try:
            session.save()
        except Exception as e:
            console.print(f"[dim]Warning: Could not save session: {e}[/dim]")

        console.print(f"\n[{GOLD}]👋 Goodbye! Session ended.[/{GOLD}]")
        display_session_summary(session)
        return True

    elif command in ['clear', 'reset', 'new']:
        # Clear conversation context
        archives.clear()
        console.print(f"\n[{GREEN}]✓ Conversation history cleared![/{GREEN}]")
        console.print(f"[dim]Starting fresh with empty context.[/dim]\n")
        return False

    elif command in ['config', 'settings']:
        # Show config info (don't run full wizard in session)
        console.print(f"\n[{CYAN}]Current Configuration:[/{CYAN}]")
        console.print(f"[dim]  Bishops: {', '.join(settings.bishop_models)}[/dim]")
        console.print(f"[dim]  Pope: {settings.pope_model}[/dim]")
        console.print(f"\n[dim]Run 'synod config' outside the session to change settings.[/dim]\n")
        return False

    elif command == 'bishops':
        # Show bishops
        console.print(f"\n[{CYAN}]Your Bishops:[/{CYAN}]")
        for i, bishop in enumerate(settings.bishop_models, 1):
            name = bishop.split('/')[-1] if '/' in bishop else bishop
            console.print(f"[dim]  {i}. {name}[/dim]")
        console.print(f"\n[{GOLD}]Pope:[/{GOLD}] {settings.pope_model.split('/')[-1]}\n")
        return False

    elif command == 'pope':
        # Show pope
        pope_name = settings.pope_model.split('/')[-1] if '/' in settings.pope_model else settings.pope_model
        console.print(f"\n[{GOLD}]👑 Pope:[/{GOLD}] {pope_name}")
        console.print(f"[dim]  Full ID: {settings.pope_model}[/dim]")
        console.print(f"\n[dim]Run 'synod config' outside the session to change the pope.[/dim]\n")
        return False

    elif command == 'cost':
        # Show cost summary
        console.print(f"\n[{CYAN}]Session Cost Summary:[/{CYAN}]")
        console.print(f"[dim]  Total Tokens: {session.total_tokens:,}[/dim]")
        console.print(f"[dim]  Total Cost: ${session.total_cost:.4f}[/dim]")
        console.print(f"[dim]  Debates: {session.debates}[/dim]\n")
        return False

    elif command == 'context':
        # Show context usage
        from synod.core.session import get_model_context_limit
        context_limit = get_model_context_limit(settings.pope_model)
        tokens_used = session.total_tokens
        percentage = (tokens_used / context_limit) * 100 if context_limit > 0 else 0

        console.print(f"\n[{CYAN}]Context Usage:[/{CYAN}]")
        console.print(f"[dim]  Pope Model: {settings.pope_model.split('/')[-1]}[/dim]")
        console.print(f"[dim]  Context Limit: {context_limit:,} tokens[/dim]")
        console.print(f"[dim]  Used: {tokens_used:,} tokens ({percentage:.1f}%)[/dim]")
        console.print(f"[dim]  Available: {context_limit - tokens_used:,} tokens[/dim]\n")
        return False

    elif command in ['help', '?']:
        # Show help with all commands
        console.print(f"\n[{CYAN}]Available Commands:[/{CYAN}]\n")

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Command", style=CYAN, width=25)
        table.add_column("Description", style="dim")

        for cmd in get_all_commands():
            display = cmd.display_name
            table.add_row(display, cmd.description)

        console.print(table)
        console.print(f"\n[dim]Type / followed by a command name, or just / to see the menu.[/dim]\n")
        return False

    elif command == 'compact':
        # Compact conversation
        console.print(f"\n[{CYAN}]Compacting conversation history...[/{CYAN}]")
        # Archives auto-compact, but we can trigger it
        archives.compact()
        console.print(f"[{GREEN}]✓ Conversation compacted![/{GREEN}]\n")
        return False

    elif command in ['version', 'v']:
        # Show version
        console.print(f"\n[{CYAN}]Synod v{VERSION}[/{CYAN}]")
        console.print(f"[dim]{TAGLINE_FULL}[/dim]\n")
        return False

    elif command == 'history':
        # Show recent history
        from synod.core.session import get_recent_sessions
        sessions = get_recent_sessions(limit=5)

        if not sessions:
            console.print(f"\n[{CYAN}]No session history found.[/{CYAN}]\n")
        else:
            console.print(f"\n[{CYAN}]Recent Sessions:[/{CYAN}]\n")
            for s in sessions:
                date_str = datetime.fromtimestamp(s.start_time).strftime("%Y-%m-%d %H:%M")
                console.print(f"[dim]  {date_str} - {s.debates} debates, ${s.total_cost:.4f}[/dim]")
            console.print()
        return False

    elif command == 'stats':
        # Show detailed stats
        display_session_summary(session)
        return False

    elif command in ['index', 'reindex']:
        # Re-index workspace
        console.print(f"\n[{CYAN}]Re-indexing workspace...[/{CYAN}]")
        project_path = os.getcwd()
        indexed = quick_index(project_path, force=True)
        file_count = len(indexed.files) if indexed else 0
        console.print(f"[{GREEN}]✓ Indexed {file_count} files[/{GREEN}]\n")
        return False

    elif command == 'files':
        # List indexed files - use quick_index which loads from cache
        indexed = quick_index(os.getcwd())

        if not indexed or not indexed.files:
            console.print(f"\n[{CYAN}]No files indexed yet.[/{CYAN}]")
            console.print(f"[dim]Run /index to index the workspace.[/dim]\n")
        else:
            console.print(f"\n[{CYAN}]Indexed Files ({len(indexed.files)}):[/{CYAN}]")
            for f in indexed.files[:20]:  # Show first 20
                console.print(f"[dim]  {f}[/dim]")
            if len(indexed.files) > 20:
                console.print(f"[dim]  ... and {len(indexed.files) - 20} more[/dim]")
            console.print()
        return False

    elif command == 'add':
        # Add files to context
        if not args:
            console.print(f"\n[{ACCENT}]Usage: /add <file_path>[/{ACCENT}]")
            console.print(f"[dim]Add a file to the conversation context.[/dim]\n")
        else:
            file_path = args.strip()
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # Add as a synthetic exchange so it appears in context
                    archives.add_exchange(
                        query=f"[User added file: {file_path}]",
                        synthesis=f"```\n{content[:5000]}\n```" if len(content) > 5000 else f"```\n{content}\n```"
                    )
                    console.print(f"[{GREEN}]✓ Added {file_path} to context[/{GREEN}]\n")
                except Exception as e:
                    console.print(f"[{ACCENT}]Could not read file: {e}[/{ACCENT}]\n")
            else:
                console.print(f"[{ACCENT}]File not found: {file_path}[/{ACCENT}]\n")
        return False

    else:
        # Unknown command (shouldn't reach here if get_command worked)
        console.print(f"[{ACCENT}]Command /{command} not implemented yet.[/{ACCENT}]\n")
        return False


async def _interactive_session():
    """Interactive REPL-style session with message queuing."""
    # Ensure configured first
    await ensure_configured()

    # Check workspace trust before indexing
    from synod.core.workspace import check_workspace_trust
    project_path = os.getcwd()

    if not await check_workspace_trust(project_path):
        # User declined to trust workspace - exit
        import sys
        sys.exit(0)

    # Index project files (silently if already indexed, with progress if new)
    from synod.core.indexer import is_workspace_indexed
    already_indexed = is_workspace_indexed(project_path)

    if not already_indexed:
        console.print(f"\n[{CYAN}]📂 Indexing workspace for intelligent context suggestions...[/{CYAN}]")

    indexed_project = quick_index(project_path)
    file_count = len(indexed_project.files) if indexed_project else 0

    # Get settings for launch screen (fix UnboundLocalError)
    synod_settings = SynodSettings()
    show_launch_screen(
        version=VERSION,
        project_path=project_path,
        file_count=file_count,
        bishops=synod_settings.bishop_models,
        pope=synod_settings.pope_model,
        animate=True,  # Enable animation
    )

    # Show welcome
    welcome_text = Text()
    welcome_text.append("Synod Interactive Session\n", style=f"bold {PRIMARY}")
    welcome_text.append("Type your queries or 'exit' to quit\n", style="dim")
    welcome_text.append("💡 Tip: Context persists across queries with auto-compacting!", style=f"{GOLD}")

    console.print(Panel(welcome_text, border_style=PRIMARY, box=HEAVY))
    console.print()

    # Initialize Council Archives for context management
    archives = CouncilArchives(max_tokens=100000)

    # Initialize chat interface
    chat = SynodChatInterface()

    message_queue = []

    while True:
        try:
            # Show context usage before prompt
            session = get_current_session()

            # Get Pope's model from settings (the limiting factor)
            from synod.core.session import get_model_context_limit

            pope_model = synod_settings.pope_model
            context_limit = get_model_context_limit(pope_model)

            # Total tokens across ALL bishops (aggregate)
            tokens_used = session.total_tokens
            tokens_remaining = context_limit - tokens_used
            percentage_used = (tokens_used / context_limit) * 100 if context_limit > 0 else 0

            # Format context display
            if percentage_used < 50:
                context_color = GREEN
            elif percentage_used < 75:
                context_color = GOLD
            else:
                context_color = "red"

            # Simplified display: just show total tokens and Pope's capacity
            pope_name = pope_model.split('/')[-1] if '/' in pope_model else pope_model
            context_display = Text()
            context_display.append(f"[Synod: {tokens_used:,} tokens | ", style="dim")
            context_display.append(f"Pope {pope_name[:20]}", style="dim")
            context_display.append(f": {percentage_used:.0f}% full", style=f"{context_color}")
            context_display.append("]", style="dim")

            # Warn if approaching context limit
            if percentage_used >= 90:
                console.print(f"\n[bold red]⚠️  Pope's context is {percentage_used:.0f}% full! Consider starting fresh.[/bold red]")
            elif percentage_used >= 75:
                console.print(f"\n[{GOLD}]💡 Pope's context is {percentage_used:.0f}% full. May need to summarize soon.[/{GOLD}]")

            # Display context above the prompt
            console.print(context_display)

            # Get input from chat interface
            try:
                user_input = await chat.get_input()
            except EOFError:
                # User pressed Ctrl+D - exit gracefully
                from synod.core.session import display_session_summary
                session = get_current_session()

                try:
                    session.save()
                except Exception as e:
                    console.print(f"[dim]Warning: Could not save session: {e}[/dim]")

                console.print(f"\n[{GOLD}]👋 Goodbye! Session ended.[/{GOLD}]")
                display_session_summary(session)
                break

            if not user_input.strip():
                continue

            # Check for slash commands first
            if user_input.strip().startswith('/'):
                command_name, args = parse_slash_command(user_input)

                if command_name:
                    cmd = get_command(command_name)

                    if cmd:
                        # Handle built-in commands
                        should_exit = await _handle_slash_command(
                            cmd.name, args, session, archives, synod_settings
                        )
                        if should_exit:
                            break
                        continue
                    else:
                        console.print(f"[{ACCENT}]Unknown command: /{command_name}[/{ACCENT}]")
                        console.print(f"[dim]Type / to see available commands[/dim]\n")
                        continue

            # Check for exit commands (explicit or natural language)
            exit_commands = ['exit', 'quit', 'q', 'bye', 'goodbye', 'stop']
            if user_input.strip().lower() in exit_commands:
                # Save and show session summary before exiting
                from synod.core.session import display_session_summary
                session = get_current_session()

                # Save session to disk
                try:
                    session.save()
                except Exception as e:
                    console.print(f"[dim]Warning: Could not save session: {e}[/dim]")

                # Display summary
                console.print(f"\n[{GOLD}]👋 Goodbye! Session ended.[/{GOLD}]")
                display_session_summary(session)
                break

            # Run query (skip config check since we already ensured at start)
            try:
                await _arun_query(user_input, "", skip_config_check=True, archives=archives)
                console.print()

                # Process queued messages if any
                if message_queue:
                    console.print(f"[{GOLD}]📬 Processing {len(message_queue)} queued message(s)...[/{GOLD}]\n")
                    for queued_msg in message_queue:
                        console.print(f"[{PRIMARY}]synod>[/{PRIMARY}] {queued_msg}")
                        await _arun_query(queued_msg, "", skip_config_check=True, archives=archives)
                        console.print()
                    message_queue.clear()
            except Exception as e:
                # Catch any error during query execution and continue the loop
                console.print(f"\n[bold red]Error: {str(e)}[/bold red]")
                console.print(f"[dim]The session will continue. Type 'exit' to quit.[/dim]\n")
                continue

        except KeyboardInterrupt:
            console.print()  # New line after Ctrl+C
            # Save and show session summary before exiting
            from synod.core.session import display_session_summary
            session = get_current_session()

            # Save session to disk
            try:
                session.save()
            except Exception as e:
                console.print(f"[dim]Warning: Could not save session: {e}[/dim]")

            # Display summary
            display_session_summary(session)
            break
        except EOFError:
            break

def main():
    """Main entry point. Always launches interactive mode."""
    app()

if __name__ == "__main__":
    main()
