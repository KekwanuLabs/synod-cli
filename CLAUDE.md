# Synod CLI - Development Guidelines

## Overview

Synod CLI is the command-line interface for Synod. It's a thin client that communicates with Synod Cloud for all AI operations, while handling local tool execution and file operations.

## Tech Stack

- **Language**: Python 3.8+
- **CLI Framework**: Typer + Rich
- **Async**: asyncio + httpx
- **Package Management**: uv

## Key Files

| File | Purpose |
|------|---------|
| `synod/cli.py` | Main entry point, interactive REPL |
| `synod/core/cloud_debate.py` | SSE streaming, Rich display, status bar |
| `synod/core/chat_interface.py` | prompt_toolkit-based input |
| `synod/tools/` | Local tool execution (file ops, shell) |
| `synod/core/auto_context.py` | Automatic file context gathering |

## Architecture

```
User Input → CLI → Cloud API (SSE) → Display
                        ↓
                Tool Calls (local execution)
                        ↓
                Tool Results → Cloud API (continue)
```

## Key Patterns

### Rich Live Display

The CLI uses Rich's `Live` context for real-time updates:

```python
with Live(console=console, refresh_per_second=12, transient=True) as live:
    async for event in stream:
        handle_event(state, event)
        live.update(build_display(state))
```

### SSE Streaming with Animations

Animation frames advance on timeout to keep the UI responsive:

```python
try:
    event = await asyncio.wait_for(event_iter.__anext__(), timeout=0.1)
    handle_event(state, event)
except asyncio.TimeoutError:
    advance_animation()
    live.update(build_display(state))
```

### Status Bar

Dynamic status bar shows:
- Current action with animated ellipsis
- Parallel activities (bishops/critiques)
- Elapsed time
- Token counter
- Wave animations

## Git Commit Guidelines

**IMPORTANT**: When making commits, NEVER include:
- `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
- `Co-Authored-By: Claude` or any Claude attribution
- Any AI assistant attribution in commit messages

Use the default git author (the repository owner) for all commits. Keep commit messages clean and professional without any AI tool attribution.

## Development

```bash
# Install in dev mode
cd synod-cli
pip install -e .

# Run locally
synod

# Build and publish
uv build
uv publish
```
