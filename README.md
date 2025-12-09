# Synod

[![PyPI version](https://badge.fury.io/py/synod-cli.svg)](https://badge.fury.io/py/synod-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Ancient Councils. Modern Intelligence. Open Source.**

[Website](https://synod.run) | [Dashboard](https://synod.run/dashboard) | [PyPI](https://pypi.org/project/synod-cli/)

Synod is a CLI coding agent that harnesses multiple AI models through **adversarial debate**. Instead of relying on a single LLM, Synod orchestrates debates among multiple state-of-the-art models to produce battle-tested solutions.

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
You → Synod CLI → Synod Cloud → Multiple AI Models
                      ↓
              Adversarial Debate
                      ↓
              Best Solution ← Pope Synthesis
```

1. **You ask a question** in the CLI
2. **Synod Cloud orchestrates** a debate among AI "Bishops" (Claude, GPT, Gemini, etc.)
3. **Bishops propose solutions** independently, then **critique each other**
4. **The Pope** (most capable model) synthesizes the best answer
5. **Real-time streaming** shows debate progress as it happens

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

| Tier | Price | Debates/Day | Models |
|------|-------|-------------|--------|
| Free | $0 | 10 | 3 |
| Pro | $12/mo | Unlimited | 7 |
| Team | $29/mo | Unlimited | 7 + shared keys |

**BYOK Mode**: Use your own API keys from providers. You pay them directly, Synod just orchestrates.

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
synod> How do I implement rate limiting?
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

**Synod: Ancient Councils. Modern Intelligence. Open Source.**

[Website](https://synod.run) · [Report Bug](https://github.com/KekwanuLabs/synod-cli/issues) · [PyPI](https://pypi.org/project/synod-cli/)

</div>
