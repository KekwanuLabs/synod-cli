# Synod

[![PyPI version](https://badge.fury.io/py/synod-cli.svg)](https://badge.fury.io/py/synod-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Ancient Councils. Modern Intelligence. Open Source.**

[Website](https://synod.run) | [Dashboard](https://synod.run/dashboard) | [PyPI](https://pypi.org/project/synod-cli/)

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

## Quick Start

```bash
# Install
pipx install synod-cli

# Login (opens browser)
synod login

# Start coding
synod
```

That's it. No API keys to copy, no configuration files.

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
- 7 top AI providers: Anthropic, OpenAI, Google, xAI, DeepSeek, Zhipu, Mistral
- Adversarial critiques catch errors single models miss
- Pope synthesis combines the best ideas

### Smart & Fast
- Query classification skips debate for trivial questions
- Consensus detection exits early when models agree
- Parallel execution for speed

### Privacy-First Memory
- Learns from your sessions (patterns, not raw code)
- Semantic search across past insights
- Your code is never stored

### Beautiful CLI
- Real-time streaming with rich formatting
- Animated debate stages
- Interactive REPL mode

## Pricing

| Tier | Price | Debates/Day | Bishops |
|------|-------|-------------|---------|
| Free | $0 | 10 | 3 |
| Pro | $12/mo | Unlimited | 7 |
| Team | $29/mo | Unlimited | 7 + shared keys |

**BYOK Mode**: Bring your own API keys. You pay the providers directly, Synod just orchestrates.

## Commands

```bash
synod              # Start interactive session
synod login        # Authenticate via browser
synod logout       # Clear credentials
synod whoami       # Show current user
synod status       # Check account status
synod --help       # All commands
```

### In Interactive Mode

```
synod> How do I implement a LRU cache?
synod> /help       # Show commands
synod> /clear      # New conversation
synod> /exit       # Quit
```

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

### Data Privacy

- **Your code stays local** - Only queries and context you provide are sent to Synod Cloud
- **No raw code storage** - Synod Cloud doesn't store your code or conversation content
- **Memory is semantic** - Only extracted insights are stored as embeddings, not raw text
- **BYOK available** - Use your own API keys; we never see them (encrypted at rest)

### Credentials

- Stored locally at `~/.synod/config.json`
- API key format: `sk_...`
- Never committed to git (add `.synod/` to `.gitignore`)

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
