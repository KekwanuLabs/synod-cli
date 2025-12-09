# synod/cli.py
"""Synod CLI - Thin client for Synod Cloud.

All debate orchestration happens in the cloud. This CLI:
1. Handles user input and workspace context
2. Sends queries to Synod Cloud via SSE
3. Renders beautiful real-time output
"""
import typer
from typer import Context
from rich.panel import Panel
from rich.text import Text
from rich.box import HEAVY
import asyncio
import os
import json
import webbrowser
from pathlib import Path
from typing import Optional

from synod.core.cloud_debate import run_debate_sync
from synod.core.theme import PRIMARY, CYAN, GOLD, GREEN, SynodStyles
from synod.core.display import (
    show_launch_screen,
    animate_logo,
    console,
    get_version,
    TAGLINE_FULL,
    TAGLINE,
    SUBTITLE,
)
from synod.core.session import get_current_session
from synod.core.indexer import quick_index
from synod.core.chat_interface import SynodChatInterface
from synod.core.archives import CouncilArchives
from synod.core.slash_commands import get_command, parse_slash_command, get_all_commands

# ============================================================================
# CONFIG - API Key storage
# ============================================================================

CONFIG_DIR = Path.home() / ".synod"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    """Load config from disk."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_config(config: dict) -> None:
    """Save config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def get_api_key() -> Optional[str]:
    """Get saved API key."""
    return load_config().get("api_key")


def is_onboarded() -> bool:
    """Check if user has completed web onboarding (has API key)."""
    return get_api_key() is not None


def _typewriter_centered(text: str, color: str = "", delay: float = 0.02) -> None:
    """Print text with typewriter effect, centered."""
    import time
    import shutil
    import sys

    terminal_width = shutil.get_terminal_size().columns
    padding = (terminal_width - len(text)) // 2
    spaces = " " * max(padding, 0)

    # Use direct writes to bypass buffering
    sys.stdout = sys.__stdout__
    try:
        if color:
            sys.stdout.write(f"\033[{color}m")
        sys.stdout.write(spaces)
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(delay if char != ' ' else delay / 2)
        if color:
            sys.stdout.write("\033[0m")
        sys.stdout.write('\n')
        sys.stdout.flush()
    finally:
        pass


def show_welcome_story() -> None:
    """Show the animated welcome story (logo + narrative)."""
    import time

    # Clear screen for fresh start
    console.clear()

    # Show animated logo
    animate_logo()
    console.print()

    # Show tagline and subtitle
    console.print(
        Text(TAGLINE, style=SynodStyles.SUBTITLE),
        justify="center"
    )
    console.print(
        Text(SUBTITLE, style=SynodStyles.TAGLINE),
        justify="center"
    )

    # Version
    console.print()
    console.print(
        Text(f"v{VERSION}", style="dim"),
        justify="center"
    )

    # Storytelling with typewriter effect
    console.print()
    time.sleep(0.3)

    # Welcome
    _typewriter_centered("Welcome to Synod.", "1;38;5;208", 0.04)  # Bold orange
    time.sleep(0.5)
    console.print()

    # The story - two evocative sentences
    _typewriter_centered(
        "In ancient councils, bishops gathered to debate truth through rigorous discourse.",
        "38;5;245",  # Dim gray
        0.025
    )
    time.sleep(0.3)
    _typewriter_centered(
        "Now, AI models convene to do the same for your code.",
        "38;5;245",  # Dim gray
        0.025
    )

    time.sleep(0.6)
    console.print()


def start_login_flow() -> Optional[str]:
    """Start the browser-based login flow and return API key if successful."""
    port = _find_free_port()
    auth_url = f"https://synod.run/cli-auth?port={port}"

    console.print(f"[{CYAN}]Opening browser to sign in...[/{CYAN}]")
    console.print()

    try:
        webbrowser.open(auth_url)
    except Exception:
        console.print(f"[yellow]Could not open browser automatically.[/yellow]")
        console.print(f"Please visit: {auth_url}")
        console.print()

    console.print(f"[{GOLD}]Waiting for authentication...[/{GOLD}]")
    console.print(f"[dim]Complete sign-in in your browser. This will timeout in 2 minutes.[/dim]")
    console.print()

    # Wait for callback
    api_key = _run_callback_server(port, timeout=120)
    return api_key


def show_first_run_welcome() -> bool:
    """Show welcome for first-time users and start login flow.

    Returns True if login was successful, False otherwise.
    """
    # Show the animated story
    show_welcome_story()

    # Prompt to start login
    console.print(f"[{CYAN}]Press Enter to sign in and get started, or Ctrl+C to exit...[/{CYAN}]")
    console.print()

    try:
        input()
    except (KeyboardInterrupt, EOFError):
        return False

    # Start login flow
    api_key = start_login_flow()

    if not api_key:
        console.print(f"\n[red]Authentication timed out or was cancelled.[/red]")
        console.print(f"[dim]Run 'synod login' to try again.[/dim]\n")
        return False

    # Validate and save
    if not api_key.startswith("sk_"):
        console.print(f"\n[red]Invalid API key received.[/red]")
        console.print(f"[dim]Run 'synod login' to try again.[/dim]\n")
        return False

    # Save the key
    cfg = load_config()
    cfg["api_key"] = api_key
    save_config(cfg)

    console.print()
    console.print(f"[{GREEN}]✓ Successfully authenticated![/{GREEN}]")
    console.print()

    return True


def show_onboarding_required() -> None:
    """Show a simple message when API key is missing (for subcommands)."""
    console.print()
    console.print(f"[{GOLD}]Authentication required[/{GOLD}]")
    console.print()
    console.print(f"[dim]Run [/{dim}][{GREEN}]synod login[/{GREEN}][dim] to authenticate, or just run [/{dim}][{GREEN}]synod[/{GREEN}][dim] to get started.[/{dim}]")
    console.print()

# Version (dynamic from package metadata)
VERSION = get_version()


def version_callback(value: bool):
    if value:
        console.print(f"[{CYAN}]Synod v{VERSION}[/{CYAN}]")
        raise typer.Exit()


app = typer.Typer(
    name="synod",
    help=TAGLINE_FULL,
    add_completion=False,
    rich_markup_mode="rich",
)



async def _arun_query(prompt: str, file_context: str, archives: Optional[CouncilArchives] = None):
    """Run a query via Synod Cloud with SSE streaming.

    This is the thin client version - all debate logic happens in the cloud.
    """
    api_key = get_api_key()
    if not api_key:
        show_onboarding_required()
        return

    session = get_current_session()

    # Add archives context if provided
    full_context = file_context
    if archives:
        context_str = archives.get_context_for_debate()
        if context_str:
            full_context = f"{context_str}\n\n{file_context}" if file_context else context_str

    try:
        # Run debate via cloud with beautiful live display
        # cloud_debate.py handles all SSE streaming and panel rendering
        state = run_debate_sync(
            api_key=api_key,
            query=prompt,
            context=full_context if full_context else None,
        )

        # Record debate in session
        session.record_debate()

        # Update session with token usage from cloud
        if state.total_tokens:
            session.total_tokens += state.total_tokens
        if state.cost_usd:
            session.total_cost += state.cost_usd

        # Add exchange to archives if provided (for conversation context)
        if archives and state.pope_content:
            archives.add_exchange(
                query=prompt,
                synthesis=state.pope_content
            )

        # Handle errors from cloud
        if state.error:
            console.print(
                Panel(
                    Text(f"❌ {state.error}", style="bold red"),
                    title="[red]Error[/red]",
                    border_style="red",
                    padding=(1, 2)
                )
            )
            return

        # Display archives status if in interactive mode
        if archives:
            console.print()
            archives.display_status(console)

    except Exception as e:
        console.print(
            Panel(
                Text(f"An error occurred: {e}", style="error"),
                title="Synod Error",
                border_style="error",
            )
        )

# Single-query mode disabled - Synod is designed to be interactive only
# Use 'synod' or 'synod interactive' to start a session


@app.command()
def config(api_key: Optional[str] = typer.Argument(None, help="Your Synod API key (sk_live_...)")):
    """
    Configure your Synod API key.

    Get your API key at https://synod.run/dashboard
    All other settings (bishops, pope, BYOK) are configured on the web.
    """
    if api_key:
        # Direct API key provided as argument
        if not api_key.startswith("sk_"):
            console.print(f"\n[red]Invalid API key format. Should start with 'sk_'[/red]")
            console.print(f"[dim]Get your API key at https://synod.run/dashboard/keys[/dim]\n")
            raise typer.Exit(1)

        cfg = load_config()
        cfg["api_key"] = api_key
        save_config(cfg)

        console.print(f"\n[{GREEN}]✓ API key saved[/{GREEN}]")
        console.print(f"[dim]Run 'synod' to start an interactive session[/dim]\n")
        return

    # No API key provided - show current status or prompt
    current_key = get_api_key()

    if current_key:
        # Already configured
        masked = current_key[:10] + "..." + current_key[-4:]
        console.print(f"\n[{CYAN}]Current API key:[/{CYAN}] {masked}")
        console.print(f"\n[dim]To update, run: synod config <new-api-key>[/dim]")
        console.print(f"[dim]Manage API keys at https://synod.run/dashboard/keys[/dim]\n")

        update = typer.confirm("Would you like to update your API key?", default=False)
        if update:
            new_key = typer.prompt("Enter your new API key")
            if not new_key.startswith("sk_"):
                console.print(f"\n[red]Invalid API key format. Should start with 'sk_'[/red]\n")
                raise typer.Exit(1)

            cfg = load_config()
            cfg["api_key"] = new_key
            save_config(cfg)
            console.print(f"\n[{GREEN}]✓ API key updated[/{GREEN}]\n")
    else:
        # Not configured - show onboarding
        show_onboarding_required()

def _find_free_port() -> int:
    """Find a free port for the callback server."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', 0))
        return s.getsockname()[1]


def _run_callback_server(port: int, timeout: int = 120) -> Optional[str]:
    """Run a local HTTP server to receive the OAuth callback.

    Returns the API key if received, None if timeout.
    """
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs
    import threading

    api_key_result = {"key": None}
    server_done = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress logging

        def do_GET(self):
            parsed = urlparse(self.path)

            if parsed.path == '/callback':
                params = parse_qs(parsed.query)
                if 'key' in params:
                    api_key_result["key"] = params['key'][0]

                    # Send success response
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'''
                    <html>
                    <head>
                        <title>Synod CLI - Authorized</title>
                        <style>
                            body { font-family: -apple-system, system-ui, sans-serif; background: #0a0a0f; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                            .container { text-align: center; }
                            .check { color: #22c55e; font-size: 48px; margin-bottom: 16px; }
                            h1 { margin: 0 0 8px; }
                            p { color: #9ca3af; }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="check">&#10003;</div>
                            <h1>CLI Authorized!</h1>
                            <p>You can close this window and return to your terminal.</p>
                        </div>
                    </body>
                    </html>
                    ''')
                    server_done.set()
                else:
                    self.send_response(400)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(('localhost', port), CallbackHandler)
    server.timeout = 1  # Check every second

    # Run server with timeout
    start_time = __import__('time').time()
    while not server_done.is_set():
        server.handle_request()
        if __import__('time').time() - start_time > timeout:
            break

    server.server_close()
    return api_key_result["key"]


@app.command()
def login(
    manual: bool = typer.Option(False, "--manual", "-m", help="Use manual API key entry instead of browser flow")
):
    """
    Login to Synod Cloud.

    Opens your browser for automatic authentication. Use --manual to enter API key directly.
    """
    import httpx

    console.print()
    console.print(f"[{PRIMARY}]🔐 Synod Login[/{PRIMARY}]")
    console.print()

    # Check if already logged in
    current_key = get_api_key()
    if current_key:
        # Verify the key is still valid
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    "https://api.synod.run/me",
                    headers={"Authorization": current_key}
                )
                if response.status_code == 200:
                    data = response.json()
                    email = data.get("user", {}).get("email", "Unknown")
                    console.print(f"[{GREEN}]✓ Already logged in as {email}[/{GREEN}]")
                    console.print(f"[dim]Run 'synod logout' to switch accounts[/dim]")
                    console.print()
                    return
        except:
            pass  # Key invalid, continue with login flow

    if manual:
        # Manual API key entry - fallback mode
        console.print(f"[{CYAN}]Manual login mode[/{CYAN}]")
        console.print()
        console.print(f"[{GOLD}]Note: The automatic flow (synod login) is recommended.[/{GOLD}]")
        console.print(f"[dim]It generates an API key automatically without copy/paste.[/dim]")
        console.print()
        console.print(f"[dim]If you already have a Synod API key, enter it below.[/dim]")
        console.print(f"[dim]Keys start with 'sk_' and can be generated from synod.run/dashboard[/dim]")
        console.print()
        api_key = typer.prompt("Enter your API key")
        if not api_key.strip():
            console.print(f"\n[red]No API key provided.[/red]\n")
            raise typer.Exit(1)

        api_key = api_key.strip()
    else:
        # Automatic browser flow
        port = _find_free_port()
        auth_url = f"https://synod.run/cli-auth?port={port}"

        console.print(f"[{CYAN}]Opening browser for authentication...[/{CYAN}]")
        console.print(f"[dim]{auth_url}[/dim]")
        console.print()

        try:
            webbrowser.open(auth_url)
        except Exception:
            console.print(f"[yellow]Could not open browser automatically.[/yellow]")
            console.print(f"Please visit: {auth_url}")

        console.print(f"[{GOLD}]Waiting for authorization...[/{GOLD}]")
        console.print(f"[dim]Complete the login in your browser. This will timeout in 2 minutes.[/dim]")
        console.print()

        # Wait for callback
        api_key = _run_callback_server(port, timeout=120)

        if not api_key:
            console.print(f"\n[red]Authorization timed out or was cancelled.[/red]")
            console.print(f"[dim]Try again with 'synod login' or use 'synod login --manual'[/dim]\n")
            raise typer.Exit(1)

    # Validate key format
    if not api_key.startswith("sk_"):
        console.print(f"\n[red]Invalid API key format. Should start with 'sk_'[/red]")
        console.print(f"[dim]Get your API key at https://synod.run/dashboard/keys[/dim]\n")
        raise typer.Exit(1)

    # Verify the key works
    console.print(f"[dim]Verifying API key...[/dim]")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                "https://api.synod.run/me",
                headers={"Authorization": api_key}
            )

            if response.status_code == 401:
                console.print(f"\n[red]Invalid API key. Please check and try again.[/red]\n")
                raise typer.Exit(1)

            if response.status_code != 200:
                console.print(f"\n[red]Error verifying key: {response.text}[/red]\n")
                raise typer.Exit(1)

            data = response.json()
            email = data.get("user", {}).get("email", "Unknown")
            tier = data.get("user", {}).get("tier", "free")

    except httpx.RequestError as e:
        console.print(f"\n[red]Network error: {e}[/red]")
        console.print(f"[dim]Saving key anyway - you can verify later with 'synod status'[/dim]\n")
        email = "Unknown"
        tier = "unknown"

    # Save the key
    cfg = load_config()
    cfg["api_key"] = api_key
    save_config(cfg)

    console.print()
    console.print(f"[{GREEN}]✓ Successfully logged in as {email}[/{GREEN}]")
    console.print(f"[dim]Tier: {tier.capitalize()}[/dim]")
    console.print()
    console.print(f"[{CYAN}]Run 'synod' to start a session[/{CYAN}]")
    console.print()


@app.command()
def logout():
    """
    Logout from Synod Cloud.

    Removes your stored API key.
    """
    current_key = get_api_key()

    if not current_key:
        console.print(f"\n[dim]Not logged in.[/dim]\n")
        return

    cfg = load_config()
    cfg.pop("api_key", None)
    save_config(cfg)

    console.print(f"\n[{GREEN}]✓ Logged out successfully[/{GREEN}]")
    console.print(f"[dim]Run 'synod login' to log in again[/dim]\n")


@app.command()
def whoami():
    """
    Show current logged-in user.
    """
    import httpx

    api_key = get_api_key()
    if not api_key:
        console.print(f"\n[dim]Not logged in. Run 'synod login' to authenticate.[/dim]\n")
        return

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                "https://api.synod.run/me",
                headers={"Authorization": api_key}
            )

            if response.status_code == 401:
                console.print(f"\n[red]Session expired. Run 'synod login' to re-authenticate.[/red]\n")
                return

            if response.status_code != 200:
                console.print(f"\n[red]Error: {response.text}[/red]\n")
                return

            data = response.json()
            user = data.get("user", {})

        console.print()
        console.print(f"[{PRIMARY}]👤 Current User[/{PRIMARY}]")
        console.print(f"  Email: {user.get('email', 'Unknown')}")
        console.print(f"  Tier:  {user.get('tier', 'free').capitalize()}")
        console.print(f"  Mode:  {user.get('mode', 'byok').upper()}")
        console.print()

    except httpx.RequestError as e:
        console.print(f"\n[red]Network error: {e}[/red]\n")


@app.command()
def status():
    """Show your Synod account status and usage."""
    import httpx

    api_key = get_api_key()
    if not api_key:
        show_onboarding_required()
        return

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                "https://api.synod.run/me",
                headers={"Authorization": api_key}
            )

            if response.status_code == 401:
                console.print(f"\n[red]Invalid API key. Run 'synod config <key>' to update.[/red]\n")
                raise typer.Exit(1)

            if response.status_code != 200:
                console.print(f"\n[red]Error: {response.text}[/red]\n")
                raise typer.Exit(1)

            data = response.json()

        # Display account info
        user = data.get("user", {})
        credits = data.get("credits", {})
        usage = data.get("usage", {})
        month = usage.get("month", {})

        console.print()

        # Build status display
        status_text = Text()
        status_text.append("Account\n", style=f"bold {PRIMARY}")
        status_text.append(f"  Email:    {user.get('email', 'Unknown')}\n", style="dim")
        status_text.append(f"  Mode:     ", style="dim")
        mode = user.get('mode', 'byok').upper()
        mode_color = GREEN if mode == "BYOK" else GOLD
        status_text.append(f"{mode}\n", style=f"bold {mode_color}")
        status_text.append(f"  Credits:  ", style="dim")
        status_text.append(f"${credits.get('balance', 0):.2f}\n\n", style=f"bold {GOLD}")

        status_text.append("This Month\n", style=f"bold {PRIMARY}")
        status_text.append(f"  Debates:  {month.get('debates', 0)}\n", style="dim")
        status_text.append(f"  Tokens:   {month.get('tokens', 0):,}\n", style="dim")
        status_text.append(f"  Cost:     ${month.get('cost', 0):.2f}\n", style="dim")

        console.print(Panel(
            status_text,
            title=f"[{CYAN}]Synod Status[/{CYAN}]",
            border_style=CYAN,
            padding=(1, 2)
        ))
        console.print()

    except httpx.RequestError as e:
        console.print(f"\n[red]Connection error: {e}[/red]")
        console.print(f"[dim]Check your internet connection[/dim]\n")
        raise typer.Exit(1)


# Main callback - handles default behavior and --version
@app.callback(invoke_without_command=True)
def default_command(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True, help="Show version"),
):
    """
    Synod - Interactive AI coding debates.

    Start chatting with multiple AI models that debate to find the best solution.
    """
    if ctx.invoked_subcommand is None:
        # No command provided, launch interactive mode
        if not is_onboarded():
            # First time user - show welcome and auto-start login
            if show_first_run_welcome():
                # Login successful - proceed to interactive session
                asyncio.run(_interactive_session())
            # If login failed, show_first_run_welcome already printed error message
        else:
            # Already configured - launch interactive mode directly
            asyncio.run(_interactive_session())


async def _handle_slash_command(
    command: str,
    args: str,
    session,
    archives,
) -> bool:
    """Handle a slash command.

    Args:
        command: Command name (without /)
        args: Arguments passed to the command
        session: Current session
        archives: Council archives

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
        # Open settings in browser
        console.print(f"\n[{CYAN}]Opening settings in browser...[/{CYAN}]")
        console.print(f"[dim]Configure bishops, pope, and BYOK mode at synod.run[/dim]\n")
        webbrowser.open("https://synod.run/dashboard/settings")
        return False

    elif command in ['bishops', 'pope']:
        # Open settings in browser
        console.print(f"\n[{CYAN}]Bishop and Pope selection is done on the web.[/{CYAN}]")
        console.print(f"[dim]Opening dashboard...[/dim]\n")
        webbrowser.open("https://synod.run/dashboard/settings")
        return False

    elif command == 'cost':
        # Show cost summary
        console.print(f"\n[{CYAN}]Session Cost Summary:[/{CYAN}]")
        console.print(f"[dim]  Total Tokens: {session.total_tokens:,}[/dim]")
        console.print(f"[dim]  Total Cost: ${session.total_cost:.4f}[/dim]")
        console.print(f"[dim]  Debates: {session.debates}[/dim]\n")
        return False

    elif command == 'context':
        # Show context usage (simplified - no local pope model)
        tokens_used = session.total_tokens
        console.print(f"\n[{CYAN}]Session Context:[/{CYAN}]")
        console.print(f"[dim]  Total Tokens: {tokens_used:,}[/dim]")
        console.print(f"[dim]  View full usage at synod.run/dashboard[/dim]\n")
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
    # Safety check - main flow should have already ensured API key exists
    if not is_onboarded():
        console.print(f"\n[red]Not authenticated. Run 'synod login' first.[/red]\n")
        return

    # Clear screen for fresh start
    console.clear()

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

    # Show launch screen (bishops/pope selected in cloud)
    show_launch_screen(
        version=VERSION,
        project_path=project_path,
        file_count=file_count,
        bishops=None,  # Selected in cloud
        pope=None,  # Selected in cloud
        animate=True,
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

            # Simple token display (detailed info from cloud)
            tokens_used = session.total_tokens
            context_display = Text()
            context_display.append(f"[Synod: {tokens_used:,} tokens used", style="dim")
            if session.total_cost > 0:
                context_display.append(f" | ${session.total_cost:.4f}", style="dim")
            context_display.append("]", style="dim")

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
                            cmd.name, args, session, archives
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

            # Run query via cloud
            try:
                await _arun_query(user_input, "", archives=archives)
                console.print()

                # Process queued messages if any
                if message_queue:
                    console.print(f"[{GOLD}]📬 Processing {len(message_queue)} queued message(s)...[/{GOLD}]\n")
                    for queued_msg in message_queue:
                        console.print(f"[{PRIMARY}]synod>[/{PRIMARY}] {queued_msg}")
                        await _arun_query(queued_msg, "", archives=archives)
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
