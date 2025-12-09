"""Git integration for Synod.

Provides AI-powered git operations:
- /commit - Generate commit messages via debate
- /pr - Create PRs with debate-synthesized descriptions
- /diff - Analyze current changes
"""

import subprocess
import os
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.prompt import Confirm

from .theme import PRIMARY, CYAN, GREEN, GOLD, GRAY

console = Console()


# ============================================================================
# GIT UTILITIES
# ============================================================================

def is_git_repo(path: str = ".") -> bool:
    """Check if the current directory is a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_git_root(path: str = ".") -> Optional[str]:
    """Get the root directory of the git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def get_current_branch() -> Optional[str]:
    """Get the current git branch name."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def get_git_status() -> Tuple[List[str], List[str], List[str]]:
    """Get git status as lists of files.

    Returns:
        Tuple of (staged, unstaged, untracked) file lists
    """
    staged = []
    unstaged = []
    untracked = []

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                status = line[:2]
                filename = line[3:]

                # Staged changes (index)
                if status[0] in "MADRC":
                    staged.append(filename)
                # Unstaged changes (working tree)
                if status[1] in "MDRC":
                    unstaged.append(filename)
                # Untracked files
                if status == "??":
                    untracked.append(filename)
    except FileNotFoundError:
        pass

    return staged, unstaged, untracked


def get_git_diff(staged: bool = False, files: Optional[List[str]] = None) -> str:
    """Get git diff output.

    Args:
        staged: If True, show staged changes (--cached)
        files: Optional list of files to diff

    Returns:
        Diff output as string
    """
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--cached")
    if files:
        cmd.extend(files)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout
    except FileNotFoundError:
        pass
    return ""


def get_recent_commits(count: int = 5) -> List[Dict[str, str]]:
    """Get recent commit messages for style reference.

    Returns:
        List of dicts with 'hash', 'subject', 'body'
    """
    commits = []
    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--format=%H|||%s|||%b|||END"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for entry in result.stdout.split("|||END"):
                parts = entry.strip().split("|||")
                if len(parts) >= 2:
                    commits.append({
                        "hash": parts[0][:8],
                        "subject": parts[1],
                        "body": parts[2] if len(parts) > 2 else "",
                    })
    except FileNotFoundError:
        pass
    return commits


def stage_files(files: List[str]) -> bool:
    """Stage files for commit."""
    try:
        result = subprocess.run(
            ["git", "add"] + files,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def create_commit(message: str) -> Tuple[bool, str]:
    """Create a git commit.

    Returns:
        Tuple of (success, output/error message)
    """
    try:
        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True, result.stdout
        return False, result.stderr
    except FileNotFoundError:
        return False, "Git not found"


def push_branch(branch: Optional[str] = None, set_upstream: bool = False) -> Tuple[bool, str]:
    """Push to remote.

    Returns:
        Tuple of (success, output/error message)
    """
    cmd = ["git", "push"]
    if set_upstream and branch:
        cmd.extend(["-u", "origin", branch])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, result.stdout
        return False, result.stderr
    except FileNotFoundError:
        return False, "Git not found"


def get_remote_url() -> Optional[str]:
    """Get the remote origin URL."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def parse_github_url(url: str) -> Optional[Tuple[str, str]]:
    """Parse GitHub URL to get owner/repo.

    Returns:
        Tuple of (owner, repo) or None
    """
    import re

    # SSH format: git@github.com:owner/repo.git
    ssh_match = re.match(r"git@github\.com:(.+)/(.+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # HTTPS format: https://github.com/owner/repo.git
    https_match = re.match(r"https://github\.com/(.+)/(.+?)(?:\.git)?$", url)
    if https_match:
        return https_match.group(1), https_match.group(2)

    return None


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

async def handle_diff_command(args: str = "") -> None:
    """Handle /diff command - show and analyze current changes."""
    if not is_git_repo():
        console.print("[red]Not a git repository[/red]")
        return

    staged, unstaged, untracked = get_git_status()

    # Build status panel
    status_text = Text()

    if not staged and not unstaged and not untracked:
        console.print(Panel(
            "[green]Working directory clean - no changes to show[/green]",
            title="[cyan]Git Status[/cyan]",
            border_style="cyan"
        ))
        return

    if staged:
        status_text.append("Staged for commit:\n", style=f"bold {GREEN}")
        for f in staged[:10]:
            status_text.append(f"  ✓ {f}\n", style=GREEN)
        if len(staged) > 10:
            status_text.append(f"  ... and {len(staged) - 10} more\n", style="dim")
        status_text.append("\n")

    if unstaged:
        status_text.append("Modified (not staged):\n", style=f"bold {GOLD}")
        for f in unstaged[:10]:
            status_text.append(f"  ● {f}\n", style=GOLD)
        if len(unstaged) > 10:
            status_text.append(f"  ... and {len(unstaged) - 10} more\n", style="dim")
        status_text.append("\n")

    if untracked:
        status_text.append("Untracked files:\n", style="bold dim")
        for f in untracked[:5]:
            status_text.append(f"  ? {f}\n", style="dim")
        if len(untracked) > 5:
            status_text.append(f"  ... and {len(untracked) - 5} more\n", style="dim")

    console.print(Panel(status_text, title="[cyan]Git Status[/cyan]", border_style="cyan"))

    # Show diff preview
    if staged or unstaged:
        diff_output = get_git_diff(staged=bool(staged))
        if diff_output:
            # Truncate for display
            lines = diff_output.split("\n")
            if len(lines) > 50:
                diff_output = "\n".join(lines[:50]) + f"\n... ({len(lines) - 50} more lines)"

            console.print(Panel(
                Syntax(diff_output, "diff", theme="monokai", line_numbers=False),
                title="[cyan]Changes Preview[/cyan]",
                border_style="cyan"
            ))


async def handle_commit_command(
    args: str = "",
    run_debate_fn=None,
) -> Optional[str]:
    """Handle /commit command - create commit with AI-generated message.

    Args:
        args: Optional custom commit message or flags
        run_debate_fn: Function to run a debate (injected from CLI)

    Returns:
        Commit hash if successful, None otherwise
    """
    if not is_git_repo():
        console.print("[red]Not a git repository[/red]")
        return None

    staged, unstaged, untracked = get_git_status()

    if not staged and not unstaged and not untracked:
        console.print("[yellow]Nothing to commit - working directory clean[/yellow]")
        return None

    # If nothing staged, offer to stage all
    if not staged:
        if unstaged or untracked:
            console.print("[yellow]No files staged. Would you like to stage all changes?[/yellow]")
            if Confirm.ask("Stage all changes?", default=True):
                files_to_stage = unstaged + untracked
                if stage_files(files_to_stage):
                    staged = files_to_stage
                    console.print(f"[green]Staged {len(staged)} files[/green]")
                else:
                    console.print("[red]Failed to stage files[/red]")
                    return None
            else:
                console.print("[dim]Use 'git add <files>' to stage specific files[/dim]")
                return None

    # Get the diff for context
    diff = get_git_diff(staged=True)
    if not diff:
        console.print("[yellow]No changes to commit[/yellow]")
        return None

    # Get recent commits for style reference
    recent = get_recent_commits(5)
    style_reference = "\n".join([f"- {c['subject']}" for c in recent]) if recent else "No previous commits"

    # If custom message provided, use it
    if args.strip():
        commit_message = args.strip()
    elif run_debate_fn:
        # Run a debate to generate commit message
        console.print(f"\n[{CYAN}]🎓 Generating commit message via debate...[/{CYAN}]\n")

        query = f"""Generate a concise, conventional commit message for these changes.

## Recent commit messages (follow this style):
{style_reference}

## Changes to commit:
```diff
{diff[:8000]}  # Truncate if too long
```

Requirements:
1. Use conventional commit format: type(scope): description
2. Types: feat, fix, docs, style, refactor, test, chore
3. Keep subject line under 72 characters
4. Be specific about what changed
5. Return ONLY the commit message, nothing else"""

        state = await run_debate_fn(query=query, context=None)

        if state and state.pope_content:
            # Extract just the commit message (first line or content)
            commit_message = state.pope_content.strip().split("\n")[0]
            # Clean up any markdown or extra formatting
            commit_message = commit_message.strip("`").strip('"').strip("'")
        else:
            console.print("[yellow]Debate failed, please provide a commit message manually[/yellow]")
            return None
    else:
        console.print("[yellow]No debate function available, please provide a commit message[/yellow]")
        return None

    # Show the commit message and confirm
    console.print(Panel(
        Text(commit_message, style="bold white"),
        title="[green]Commit Message[/green]",
        border_style="green"
    ))

    if not Confirm.ask("Create commit with this message?", default=True):
        console.print("[dim]Commit cancelled[/dim]")
        return None

    # Create the commit
    success, output = create_commit(commit_message)

    if success:
        console.print(f"[green]✓ Commit created successfully[/green]")
        console.print(f"[dim]{output}[/dim]")

        # Ask about pushing
        branch = get_current_branch()
        if branch and Confirm.ask(f"Push to origin/{branch}?", default=False):
            push_success, push_output = push_branch(branch, set_upstream=True)
            if push_success:
                console.print(f"[green]✓ Pushed to origin/{branch}[/green]")
            else:
                console.print(f"[red]Push failed: {push_output}[/red]")

        return commit_message
    else:
        console.print(f"[red]Commit failed: {output}[/red]")
        return None


async def handle_pr_command(
    args: str = "",
    run_debate_fn=None,
) -> Optional[str]:
    """Handle /pr command - create PR with debate-synthesized description.

    Args:
        args: Optional PR title or flags
        run_debate_fn: Function to run a debate

    Returns:
        PR URL if successful, None otherwise
    """
    if not is_git_repo():
        console.print("[red]Not a git repository[/red]")
        return None

    # Check if gh CLI is available
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print("[red]GitHub CLI (gh) not found. Install it from https://cli.github.com[/red]")
        return None

    branch = get_current_branch()
    if not branch:
        console.print("[red]Could not determine current branch[/red]")
        return None

    if branch in ["main", "master"]:
        console.print("[yellow]Cannot create PR from main/master branch[/yellow]")
        return None

    # Get commits on this branch (vs main)
    try:
        result = subprocess.run(
            ["git", "log", "main..HEAD", "--oneline"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Try master
            result = subprocess.run(
                ["git", "log", "master..HEAD", "--oneline"],
                capture_output=True,
                text=True,
            )
        commits = result.stdout.strip() if result.returncode == 0 else ""
    except FileNotFoundError:
        commits = ""

    if not commits:
        console.print("[yellow]No commits found on this branch[/yellow]")
        return None

    # Get diff vs main
    try:
        result = subprocess.run(
            ["git", "diff", "main...HEAD"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["git", "diff", "master...HEAD"],
                capture_output=True,
                text=True,
            )
        diff = result.stdout if result.returncode == 0 else ""
    except FileNotFoundError:
        diff = ""

    # Generate PR description via debate
    if run_debate_fn:
        console.print(f"\n[{CYAN}]🎓 Generating PR description via debate...[/{CYAN}]\n")

        query = f"""Generate a pull request description for these changes.

## Branch: {branch}

## Commits on this branch:
{commits}

## Changes (diff):
```diff
{diff[:10000]}
```

Generate a PR description with:
1. ## Summary - 2-3 bullet points of what changed
2. ## Changes - List of specific changes
3. ## Testing - How to test these changes

Keep it concise and actionable. Return ONLY the PR description in markdown."""

        state = await run_debate_fn(query=query, context=None)

        if state and state.pope_content:
            pr_body = state.pope_content.strip()
        else:
            console.print("[yellow]Debate failed, using simple description[/yellow]")
            pr_body = f"## Changes\n\n{commits}"
    else:
        pr_body = f"## Changes\n\n{commits}"

    # Generate title from branch name or first commit
    pr_title = args.strip() if args.strip() else branch.replace("-", " ").replace("_", " ").title()

    # Show preview
    console.print(Panel(
        f"**Title:** {pr_title}\n\n{pr_body}",
        title="[green]PR Preview[/green]",
        border_style="green"
    ))

    if not Confirm.ask("Create this PR?", default=True):
        console.print("[dim]PR cancelled[/dim]")
        return None

    # Push branch first
    push_success, push_output = push_branch(branch, set_upstream=True)
    if not push_success:
        console.print(f"[yellow]Warning: Push may have failed: {push_output}[/yellow]")

    # Create PR with gh
    try:
        result = subprocess.run(
            ["gh", "pr", "create", "--title", pr_title, "--body", pr_body],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            pr_url = result.stdout.strip()
            console.print(f"[green]✓ PR created: {pr_url}[/green]")
            return pr_url
        else:
            console.print(f"[red]PR creation failed: {result.stderr}[/red]")
            return None
    except FileNotFoundError:
        console.print("[red]GitHub CLI not found[/red]")
        return None


# ============================================================================
# PR REVIEW MODE
# ============================================================================

async def review_pr(
    pr_number: Optional[int] = None,
    run_debate_fn=None,
) -> None:
    """Run adversarial review on a PR.

    Args:
        pr_number: PR number to review (or current branch's PR)
        run_debate_fn: Function to run a debate
    """
    if not is_git_repo():
        console.print("[red]Not a git repository[/red]")
        return

    # Check gh CLI
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print("[red]GitHub CLI (gh) not found[/red]")
        return

    # Get PR info
    if pr_number:
        pr_cmd = ["gh", "pr", "view", str(pr_number), "--json", "title,body,additions,deletions,files"]
    else:
        pr_cmd = ["gh", "pr", "view", "--json", "title,body,additions,deletions,files"]

    try:
        result = subprocess.run(pr_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Could not get PR info: {result.stderr}[/red]")
            return

        import json
        pr_info = json.loads(result.stdout)
    except Exception as e:
        console.print(f"[red]Error getting PR: {e}[/red]")
        return

    # Get PR diff
    if pr_number:
        diff_cmd = ["gh", "pr", "diff", str(pr_number)]
    else:
        diff_cmd = ["gh", "pr", "diff"]

    result = subprocess.run(diff_cmd, capture_output=True, text=True)
    diff = result.stdout if result.returncode == 0 else ""

    console.print(Panel(
        f"**{pr_info.get('title', 'PR')}**\n\n"
        f"+{pr_info.get('additions', 0)} -{pr_info.get('deletions', 0)} lines\n"
        f"{len(pr_info.get('files', []))} files changed",
        title=f"[cyan]Reviewing PR #{pr_number or 'current'}[/cyan]",
        border_style="cyan"
    ))

    if run_debate_fn:
        query = f"""You are reviewing a pull request. Perform an adversarial code review.

## PR Title: {pr_info.get('title', 'Unknown')}

## PR Description:
{pr_info.get('body', 'No description')}

## Changes:
```diff
{diff[:15000]}
```

Provide a thorough code review covering:
1. 🔴 CRITICAL issues (bugs, security vulnerabilities, data loss risks)
2. 🟡 MODERATE issues (performance, edge cases, error handling)
3. 🟢 MINOR issues (style, naming, documentation)
4. ✅ What's good about this PR

Be specific - quote code, explain the problem, suggest fixes.
Format as a proper code review with actionable feedback."""

        await run_debate_fn(query=query, context=None)
    else:
        console.print("[yellow]No debate function available for review[/yellow]")
