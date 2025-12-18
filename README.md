# Synod

[![PyPI version](https://badge.fury.io/py/synod-cli.svg)](https://badge.fury.io/py/synod-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Ancient Councils. Modern Intelligence. Adversarial Memory.**

> *An AI coding agent where mistakes don't survive peer review.*

[Website](https://synod.run) | [Dashboard](https://synod.run/dashboard) | [PyPI](https://pypi.org/project/synod-cli/)

---

<div align="center">

### Why Synod?

| Problem | Synod Solution |
|---------|----------------|
| Single AI hallucinates | **Multiple models catch each other's mistakes** |
| Context limits run out | **Infinite memory that never forgets** |
| No memory between sessions | **Battle-tested insights persist forever** |
| Can't trust AI suggestions | **Every answer survives adversarial review** |

</div>

---

*In ancient councils, bishops gathered to debate truth through rigorous discourse.*

*Now, AI models convene to do the same for your code.*

---

## The Story

For centuries, the most important decisions weren't made by a single authority. They were forged through **structured debate**.

In ecclesiastical councils (called *synods*), bishops from different regions would gather, each bringing their own perspective. They'd propose, critique, and challenge each other's positions. Only after rigorous discourse would the presiding authority synthesize a final judgment, drawing from the best arguments presented.

This model of collective intelligence solved a fundamental problem: **no single perspective, however wise, captures the whole truth.**

We built Synod on the same principle.

## What is Synod?

Synod is a CLI coding agent that orchestrates **adversarial debates** among multiple AI models to solve your coding problems.

Instead of asking one AI and hoping it doesn't hallucinate, Synod convenes a council:

- **Bishops** (Claude, GPT-4, Gemini, Grok, DeepSeek, and more) independently propose solutions
- Each Bishop **critiques the others**, hunting for bugs, edge cases, and flaws
- The **Pope** (the most capable model) observes silently, then synthesizes the best answer

The result: battle-tested solutions that survive adversarial review.

## Adversarial Memory

Synod memories are **verified by multiple AI models before storage**. Every insight is battle-tested through debate.

```
┌─────────────────────────────────────────────────────────────┐
│  Synod Adversarial Memory:                                  │
│                                                             │
│    Claude ──┐                                               │
│    GPT ─────┼→ Critique each other → Pope verifies → Store │
│    Gemini ──┘                           ↑                   │
│                                   (Battle-tested)           │
│                                                             │
│  Confidence = f(consensus, critique_survival, rounds)       │
└─────────────────────────────────────────────────────────────┘
```

**Why it matters:**
- Memories from high-consensus debates get higher confidence scores
- Insights that survived adversarial critique are more trustworthy
- Skills are only learned when multiple models agreed on the approach
- Automatic decay removes stale memories over time
- Cross-project learning from your coding patterns

**What Synod remembers:**

| Memory Type | Scope | Examples |
|-------------|-------|----------|
| `preference` | User | "Prefers TypeScript over JavaScript" |
| `pattern` | User | "Often uses async/await over .then()" |
| `fact` | User | "Familiar with React and Next.js" |
| `correction` | User | "Corrected: use useState not useRef" |
| `skill` | User (Pro+) | Reusable patterns from successful debates |
| `architecture` | Project | "Uses microservices with API gateway" |
| `convention` | Project | "Uses snake_case for database fields" |
| `bug` | Project | "Auth middleware has race condition" |
| `decision` | Project | "Chose PostgreSQL for ACID compliance" |

**Skills (Pro+ only):**
Skills are reusable patterns extracted from high-quality debates:
- Only extracted when consensus ≥ 70% AND no critical issues
- Stored with higher deduplication threshold (0.90)
- Automatically suggested for similar future problems

**Memory Commands:**
```bash
synod> /memory           # View memory dashboard
synod> /memory show      # Display local context files
synod> /memory graph     # Visualize memory connections (Pro)
synod> /memory timeline  # Show memory activity over time
```

## Quick Start

```bash
# Install (recommended)
pipx install synod-cli

# Or with pip
pip install synod-cli

# Login (opens browser)
synod login

# Start coding
synod
```

That's it. No API keys to copy, no configuration files.

> **Tip:** Use `pipx` for CLI tools - it installs in isolated environments and makes upgrades easy with `pipx upgrade synod-cli`

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   You: "How do I implement rate limiting?"                  │
│                                                             │
│                         ↓                                   │
│                                                             │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐                    │
│   │ Bishop  │  │ Bishop  │  │ Bishop  │   Stage 1:         │
│   │ Claude  │  │  GPT-4  │  │ Gemini  │   Proposals        │
│   └────┬────┘  └────┬────┘  └────┬────┘                    │
│        │            │            │                          │
│        └────────────┼────────────┘                          │
│                     ↓                                       │
│        ┌────────────────────────┐                          │
│        │   Adversarial Debate   │   Stage 2:               │
│        │   "Your solution has   │   Critiques              │
│        │    a race condition"   │                          │
│        └───────────┬────────────┘                          │
│                    ↓                                        │
│        ┌────────────────────────┐                          │
│        │      Pope Synthesis    │   Stage 3:               │
│        │   Best of all worlds   │   Final Answer           │
│        └────────────────────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### The Debate Process

**Stage 0: Classification**
Before convening the council, Synod analyzes your query. Trivial questions get fast answers. Complex problems get full debates.

**Stage 1: Bishop Proposals**
Multiple AI models independently propose solutions in parallel. Each brings different strengths: Claude for reasoning, GPT for breadth, DeepSeek for algorithms.

**Stage 2: Adversarial Critiques**
Here's where the magic happens. Each Bishop reviews the others' proposals like a hostile code reviewer. They hunt for:
- Bugs and edge cases
- Security vulnerabilities
- Performance issues
- Design flaws

If the Bishops agree (high consensus), we skip to synthesis. If they disagree, they debate until convergence.

**Stage 3: Pope Synthesis**
The Pope has been watching silently, observing proposals and critiques without bias. Now it synthesizes the final answer, combining the best ideas:

> *"Algorithm from DeepSeek, error handling from Claude, but I'm adding input validation they all missed."*

The Pope can override consensus if it spots a flaw everyone missed.

## Why This Works

### Single Model Problems

Ask one AI to write code. It might:
- Hallucinate an API that doesn't exist
- Miss an edge case
- Use a deprecated pattern
- Have a subtle security flaw

You won't know until runtime. Or production.

### Adversarial Debate Solution

With Synod:
- Bishop A proposes a solution
- Bishop B says "that has a race condition"
- Bishop C says "also, you're not handling the empty case"
- The Pope synthesizes a solution that addresses all critiques

**Mistakes don't survive peer review from multiple SOTA models.**

## Features

### Multi-Model Debate
- **6 AI providers**: Anthropic, OpenAI, Google, xAI, DeepSeek, Zhipu
- **Adversarial critiques** catch errors single models miss
- **Pope synthesis** combines the best ideas from each model
- **Battle-tested answers** that survive hostile code review

### Infinite Memory & Context
- **Never runs out**: Semantic memory that grows with you
- **Cross-project learning**: Patterns from one project help another
- **Verified memories**: Only insights that survived debate get stored
- **Confidence scoring**: High-consensus memories ranked higher
- **Smart retrieval**: Only relevant memories injected (no token waste)

### Smart & Fast
- **Intelligent routing**: Trivial questions get fast answers, complex problems get full debates
- **Consensus detection**: Early exit when models agree (saves tokens)
- **Parallel execution**: All bishops propose simultaneously
- **Token efficiency**: Pay for intelligence, not repetition

### Privacy-First (Zero Storage)
- **Nothing is saved**: Your queries and code are never stored on our servers
- **Pass-through only**: Data flows to AI providers and back, then it's gone
- **Memories are semantic**: Only extracted insights stored as embeddings (not raw text)
- **BYOK available**: Your API keys are encrypted at rest, never logged
- **[Read our Privacy Policy](https://synod.run/privacy)**: Our commitment to your data

### Beautiful CLI
- Real-time streaming with rich formatting
- Animated debate stages
- Interactive REPL mode

### Project Context (SYNOD.md)
Like Claude Code's CLAUDE.md, Synod reads project instructions from:
- `.synod/SYNOD.md` - Project-specific guidelines (commit to git)
- `.synod/SYNOD.local.md` - Local preferences (gitignored)
- `~/.synod/SYNOD.md` - User-wide preferences

```bash
synod> /init          # Create .synod/SYNOD.md
synod> /memory        # View loaded context
synod> /memory show   # Display full context
```

### Custom Slash Commands
Create reusable prompts as markdown files:

```bash
# Create .synod/commands/review.md
---
description: Run security review
---
Review this code for security vulnerabilities: $ARGUMENTS
```

Then use it: `synod> /review src/auth.py`

Supports `$ARGUMENTS`, `$1`, `$2` for argument interpolation.

### Git Integration
AI-powered git workflow:

```bash
synod> /diff          # Show git status and diff preview
synod> /commit        # Stage files, debate-generated commit message, push option
synod> /pr            # Create PR with debate-synthesized description (requires gh)
```

**How `/commit` works:**
1. Shows staged/unstaged files
2. Offers to stage all if nothing staged
3. Runs a debate to generate a conventional commit message
4. Shows message for confirmation
5. Creates commit and offers to push

**How `/pr` works:**
1. Gets commits and diff vs main/master
2. Runs a debate to generate PR title and description
3. Pushes branch and creates PR via GitHub CLI

### Adversarial Code Review
Run adversarial review on PRs, diffs, or files:

```bash
# CLI commands
synod review --pr 123   # Review PR #123 (requires gh)
synod review --diff     # Review uncommitted changes

# Interactive mode commands
synod> /review 123        # Review PR #123 (requires gh)
synod> /review file.py    # Review a specific file
synod> /critique a.py b.py  # Critique multiple files
```

**Requirements:**
- `/diff`, `/commit` - Just needs `git`
- `/pr`, `/review <pr-number>`, `synod review --pr` - Requires [GitHub CLI (gh)](https://cli.github.com)

### Hooks System
Automate workflows with hooks (like git hooks, but for AI):

```json
// .synod/hooks.json
{
  "hooks": [
    {
      "name": "run-tests-after-debate",
      "event": "post_debate",
      "command": "npm test 2>/dev/null || echo 'Tests skipped'"
    }
  ]
}
```

Available events: `session_start`, `session_end`, `pre_debate`, `post_debate`, `pre_tool_use`, `post_tool_use`, `file_modified`

```bash
synod> /hooks                  # List configured hooks
synod> /hooks add <name> <event> <command>
synod> /hooks remove <name>
```

### Checkpoint/Undo System
Automatic checkpoints before file changes:

```bash
synod> /rewind            # Show available checkpoints
synod> /rewind <id>       # Restore specific checkpoint
```

## Pricing

| Tier | Price | Debates/Day | Bishops | Memory |
|------|-------|-------------|---------|--------|
| Free | $0 | 10 | 3 | 1,000 memories (30-day retention) |
| Pro | $12/mo | Unlimited | 7 | Unlimited (forever) |
| Team | $29/mo | Unlimited | 7 + shared | Unlimited + shared team memory |

**BYOK Mode**: Bring your own API keys. You pay the providers directly, Synod just orchestrates.

## Commands

```bash
synod              # Start interactive session
synod login        # Authenticate via browser
synod logout       # Clear credentials
synod whoami       # Show current user
synod status       # Check account status
synod review --pr 123  # Adversarial PR review
synod review --diff    # Review uncommitted changes
synod --help       # All commands
```

### In Interactive Mode

```
synod> How do I implement a LRU cache?
synod> /help       # Show all commands
synod> /clear      # New conversation
synod> /exit       # Quit
```

### All Slash Commands

| Command | Description |
|---------|-------------|
| **Session** | |
| `/exit`, `/quit`, `/q` | Exit the session |
| `/clear`, `/reset`, `/new` | Clear conversation history |
| `/resume` | Load previous session |
| `/cost` | Show session cost |
| `/history` | View recent sessions |
| `/stats` | Detailed session statistics |
| `/compact` | Compact conversation history |
| `/rewind [id]` | Show checkpoints or restore one |
| **Git** | |
| `/diff` | Show git status and diff preview |
| `/commit [msg]` | Debate-generated commit message (or use provided) |
| `/pr [title]` | Create PR with debate description (requires `gh`) |
| **Review** | |
| `/review <file\|pr#>` | Review a file or PR number |
| `/critique <files...>` | Adversarial critique of files |
| **Memory** | |
| `/memory` | View memory dashboard |
| `/memory show` | Display local context files |
| `/memory graph` | Visualize memory connections (Pro) |
| `/memory timeline [days]` | Show memory activity timeline |
| **Configuration** | |
| `/config` | Open dashboard in browser |
| `/bishops`, `/pope` | Configure models (via web dashboard) |
| `/hooks` | List, add, or remove hooks |
| **Workspace** | |
| `/context` | Show context/token usage |
| `/index` | Re-index workspace files |
| `/files` | List indexed files |
| `/add <file>` | Add file to conversation context |
| `/search <query>` | Search codebase |
| `/init` | Create .synod/SYNOD.md |
| **General** | |
| `/help`, `/?` | Show all commands |
| `/version` | Show version |

## Security

### Workspace Trust

When you run `synod` in a directory, you'll be asked to trust the workspace:

```
Accessing workspace: /path/to/project

Safety check: Is this a project you created or trust?
The Council will be able to read, edit, and execute files here.

? Yes, I trust this workspace
  No, exit
```

**Only trust workspaces you control.** Synod can read and modify files in trusted workspaces.

### Data Privacy Promise

**We never store your queries or code. Ever.**

| What | Stored? | Details |
|------|---------|---------|
| Your queries | ❌ No | Pass-through to AI providers only |
| Your code | ❌ No | Never touches our servers |
| Conversation content | ❌ No | Discarded after response |
| Raw text | ❌ No | Only semantic embeddings for memory |
| API keys (BYOK) | 🔒 Encrypted | AES-256 at rest, never logged |
| Usage metadata | ✓ Yes | Token counts, timestamps (for billing) |

**Memory stores insights, not content.** When Synod "remembers" that you prefer TypeScript, it stores a semantic embedding of that preference, not your actual code or conversation.

Read our full [Privacy Policy](https://synod.run/privacy) for details.

### Credentials & Config Files

**User-level** (`~/.synod/`):
- `config.json` - API key and settings
- `SYNOD.md` - User-wide AI instructions
- `commands/` - Custom slash commands
- `hooks.json` - User-level hooks

**Project-level** (`.synod/`):
- `SYNOD.md` - Project guidelines (commit to git)
- `SYNOD.local.md` - Local preferences (gitignored)
- `commands/` - Project slash commands
- `hooks.json` - Project hooks
- `checkpoints/` - Auto-saved undo points

API key format: `sk_...`

## Architecture

```
┌─────────────────┐     ┌─────────────────────────────────────┐
│   Synod CLI     │────▶│          Synod Cloud                │
│  (This repo)    │◀────│  (api.synod.run)                    │
└─────────────────┘     │                                     │
                        │  ┌─────────────────────────────┐    │
                        │  │ Debate Orchestration        │    │
                        │  │ - Query classification      │    │
                        │  │ - Bishop selection          │    │
                        │  │ - Parallel proposals        │    │
                        │  │ - Adversarial critiques     │    │
                        │  │ - Pope synthesis            │    │
                        │  └─────────────────────────────┘    │
                        │                                     │
                        │  ┌─────────────────────────────┐    │
                        │  │ LLM Providers               │    │
                        │  │ Anthropic, OpenAI, Google,  │    │
                        │  │ xAI, DeepSeek, Zhipu        │    │
                        │  └─────────────────────────────┘    │
                        │                                     │
                        │  ┌─────────────────────────────┐    │
                        │  │ Memory System               │    │
                        │  │ Qdrant + Semantic Search    │    │
                        │  └─────────────────────────────┘    │
                        └─────────────────────────────────────┘
```

The CLI is a thin client. All debate orchestration happens in Synod Cloud.

## The Name

A **synod** (from Greek *σύνοδος*, "assembly") is a council of church officials convened to decide on matters of doctrine. The most famous, the Council of Nicaea in 325 AD, brought together bishops from across the Roman Empire to debate and establish foundational Christian doctrine.

We borrowed the model, not the religion:
- **Bishops**: Independent experts who propose and critique
- **Pope**: The synthesizing authority who renders final judgment
- **Debate**: Adversarial discourse that stress-tests ideas

Ancient wisdom. Modern implementation.

## Development

```bash
# Clone
git clone https://github.com/KekwanuLabs/synod-cli.git
cd synod-cli

# Install with uv
uv sync
pip install -e .

# Run
synod
```

## Contributing

| Type | How |
|------|-----|
| Bug Reports | [Open an issue](https://github.com/KekwanuLabs/synod-cli/issues) |
| Feature Requests | [Open an issue](https://github.com/KekwanuLabs/synod-cli/issues) |
| Code | Fork → Branch → PR |

## License

MIT License - Free and open source.

Copyright (c) 2025 [KekwanuLabs](https://kekwanu.com)

---

<div align="center">

*The council is always in session.*

**[synod.run](https://synod.run)**

[Report Bug](https://github.com/KekwanuLabs/synod-cli/issues) · [Request Feature](https://github.com/KekwanuLabs/synod-cli/issues) · [PyPI](https://pypi.org/project/synod-cli/)

</div>
