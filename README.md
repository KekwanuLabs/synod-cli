# Synod

[![PyPI version](https://badge.fury.io/py/synod-cli.svg)](https://badge.fury.io/py/synod-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![GitHub stars](https://img.shields.io/github/stars/KekwanuLabs/synod-cli)](https://github.com/KekwanuLabs/synod-cli/stargazers)

**Ancient Councils. Modern Intelligence. Open Source.**

Synod is a CLI-based coding agent that harnesses the collective intelligence of multiple AI models through **intelligent adversarial debate**. Instead of relying on a single LLM that might hallucinate or make mistakes, Synod orchestrates rigorous debates among multiple state-of-the-art models to produce battle-tested, robust solutions to your most challenging coding problems.

**Built for speed, accuracy, and an exceptional developer experience.**

## ⚡ Quick Start

```bash
# Install from PyPI
pip install synod-cli

# Or with pipx (recommended for CLI tools)
pipx install synod-cli

# Configure your models
synod config

# Start debating!
synod query "Implement a binary search tree with thread-safe operations"
```

## Why "Synod"? The Governance Model

Synod borrows its name from one of history's most effective decision-making frameworks: **deliberative assemblies**.

### The Framework

The synod model operated on a principle that's still powerful today:
1. **Multiple perspectives** independently analyze a problem
2. **Adversarial debate** where each perspective challenges the others
3. **Hierarchical synthesis** where a presiding authority weighs all arguments and renders final judgment

This arrangement is about **governance, deliberation, and collective intelligence**.

### Why This Maps to AI

Replace "delegates" with "AI models" and you have Synod:
- Multiple SOTA models independently propose solutions
- Each model critiques the others' proposals (adversarial review)
- A designated model (the "Pope") **synthesizes the best parts from each** into a final solution

The magic isn't in choosing one model's answer—it's in **mixing the best ideas from all of them**. Just like you used to do manually by prompting Claude, then GPT, then comparing. Now automated and enhanced.

**Collective intelligence. Modern implementation. Better code.**

## Architecture: Intelligent Adversarial Debate

When you submit a coding problem to Synod, it orchestrates a **4-stage intelligent debate** process:

### Stage 0: Pre-Debate Intelligence (FREE 🎉)
Before any debate begins, Synod analyzes your query using **Grok 4.1 Fast (free)** to determine:
- **Is it coding-related?** (Automatically rejects non-coding queries)
- **What's the complexity?** (Trivial, Simple, Moderate, Complex, Expert)
- **Which domains are involved?** (19 specialized domains: ML/AI, blockchain, security, etc.)
- **How should bishops be weighted?** (Expertise matching based on query domains)
- **What debate strategy?** (1-5 bishops, 1-5 rounds, consensus detection)

**Cost: $0** - Classification uses only free models! If classification fails, gracefully falls back to moderate complexity defaults.

### Stage 1: Weighted Initial Proposals
Your coding request is presented to **dynamically selected** Bishops based on their expertise in relevant domains. Each model independently proposes solutions in parallel. Simple queries might use 2-3 bishops; complex queries use all 5.

**Pope as Unbiased Observer:** The Pope does NOT participate in Stage 1—they silently observe all proposals without bias. This enables true synthesis without being anchored to their own proposal.

**Innovation:** Bishops are weighted 0.5-1.2x based on their domain expertise. DeepSeek V3 gets higher weight for algorithms; Claude Sonnet for architecture. All bishops stream responses in parallel with animated progress indicators.

### Stage 2: Adversarial Debate with Smart Skipping
Each Bishop acts as a hostile code reviewer, examining others' proposals for bugs, security flaws, and design issues. This isn't a polite review—it's **adversarial debate** where each model challenges the others.

**Pope as Unbiased Observer:** The Pope does NOT participate in Stage 2 critiques—they remain impartial, observing all arguments without bias.

**Consensus-Aware Prompts:** Critique intensity adapts to consensus level:
- **High consensus (90%+):** Hunt for shared blind spots - "What input would break ALL these solutions?"
- **Moderate consensus (50-90%):** Pick a winner - "Which solution would you ship? Why not the others?"
- **Low consensus (<50%):** Arbitrate disagreement - "Why do they differ? Who is RIGHT?"

**Smart Skipping:** If proposals are 85%+ similar (pairwise), redundant critiques are skipped automatically. You'll see `⏭ skipped (proposals identical)` in the UI.

### Stage 3: Active Pope Synthesis (The Magic)
The Pope (Claude Opus 4.5 by default) isn't just a passive merger—it's the **most capable model** with full authority to:

- **ADD** its own improvements where all bishops missed something
- **OVERRIDE** bishop proposals if it knows a better approach
- **CORRECT** misunderstandings if the bishops got the problem wrong
- **CHALLENGE** assumptions that all proposals share but are flawed

**Consensus-Aware Synthesis:**
- **High consensus (90%+):** Polish the agreed approach, add any missing pieces
- **Moderate (50-90%):** Cherry-pick best parts, fill gaps, make it BETTER than any individual
- **Low (<50%):** Arbitrate—analyze WHY they disagree, pick the RIGHT approach

**Example:** "Algorithm from DeepSeek, error handling from Claude, but I'm adding input validation they all missed."

**Papal Authority:** Even with 100% bishop consensus, the Pope can identify blind spots—the answer isn't always what the experts agree on.

## Why Synod is Different

### 🧠 Intelligent & Adaptive (v0.2.0)
- **FREE Pre-debate classification** - $0 cost using free models
- **Dynamic expertise weighting** - Bishops weighted by domain expertise
- **Smart LLM consensus detection** - Semantic similarity, not keyword matching
- **Adaptive rounds** - 1-5 rounds based on complexity and disagreement
- **19 specialized domains** - ML/AI, blockchain, security, algorithms, and more
- **Token budget management** - 1K-60K tokens based on query complexity

### 🛡️ Quality Control & Rigor (v0.3.0)
- **Strict trivial classification** - Only pure math/print statements skip debate (prevents wasted resources)
- **Papal veto power** - Pope can override consensus if fundamental errors detected
- **Evidence-based critiques** - Must quote code, explain why, suggest fixes (no generic feedback)
- **Smart critic pairing** - Complementary expertise matching for diverse perspectives
- **Unbiased Pope architecture** - Pope observes silently, synthesizes without bias
- **Early synthesis** - >95% consensus skips critiques entirely (speed + quality)

### 🚀 Fast Parallel Execution
Built on async/parallel execution with `asyncio` and `httpx`. All Bishops debate simultaneously, making Synod fast despite querying multiple models.

### 🎯 Minimizes Hallucinations
Adversarial debate means every solution is challenged. Mistakes don't survive the gauntlet of peer review from other SOTA models.

### 🌟 State-of-the-Art Bishop Models
Synod exclusively uses the 6 most powerful SOTA models via [OpenRouter](https://openrouter.ai):

**The 6 Bishops:**
1. **Claude Opus 4.5** - Recommended Pope (best at reasoning and synthesis)
2. **Claude Sonnet 4.5** - Fast, high-quality responses
3. **GPT 5.1 Chat** - Latest from OpenAI
4. **Grok 4.1 Fast** - xAI's fastest model
5. **Gemini 3.0** - Google's multimodal powerhouse
6. **DeepSeek V3.1** - Excellence in algorithms and optimization

**FREE Classifier** (not involved in debate):
- **Grok 4.1 Fast** - Fast, reliable, excellent availability (all classification $0)
- If unavailable, gracefully falls back to moderate complexity defaults

OpenRouter also supports Azure, AWS Bedrock, and other platforms, so you can use your existing infrastructure.

### 💎 Developer-Focused UX
- Beautiful color-coded CLI output with Rich library
- Real-time animated spinners for parallel debate stages
- Clear visualization of each debate stage (cyan proposals → magenta critiques → blue synthesis)
- Guided onboarding that walks you through setup
- Interactive model selection with live pricing and context window info
- **Always-on interactive mode** - Continues like Claude Code until you type `exit`
- Streams responses in real-time with checkmarks on completion

### 🎨 Built for Developers
- Provide file context with `-f` flags
- Configuration saved for future sessions
- Simple, intuitive commands
- Full terminal integration

### 📜 Smart Context Management
Synod uses a unique **stateless bishops, stateful Pope** architecture:

- **Bishops are stateless** - Each query gets fresh, unbiased perspectives from bishops
- **Only the Pope maintains context** - Session history flows through the Pope's synthesis
- **Auto-compacting archives** - Old exchanges are summarized to preserve context space
- **`/context` command** - Shows Pope's context usage (the only context that matters)

This design ensures cost efficiency (no multiplied context for 5+ bishops) while maintaining session continuity through the Pope's accumulated wisdom.

### 💳 Use Your Existing Cloud Credits

**Have Azure, AWS Bedrock, or Google Vertex AI credits?** Use them with Synod!

OpenRouter supports linking your cloud provider accounts, so you can:
- ✅ Use your Azure OpenAI deployments
- ✅ Use your AWS Bedrock credits
- ✅ Use your Google Vertex AI projects
- ✅ Use Anthropic API directly

**→ See [PROVIDERS.md](PROVIDERS.md) for the complete setup guide**

Quick summary:
1. Link your cloud credentials to OpenRouter (https://openrouter.ai/settings/keys)
2. Set your OpenRouter API key
3. Select your models - OpenRouter routes through your cloud accounts automatically
4. **No markup fees** - pay your cloud provider's rates directly

This means if you're already paying for Azure OpenAI or have AWS credits, you can use Synod without additional costs!

## Installation

### Option 1: pip (Recommended)
```bash
pip install synod-cli
```

### Option 2: pipx (For CLI tools)
```bash
pipx install synod-cli
```

### Option 3: uv (Fastest)
```bash
uv tool install synod-cli
```

## Setup

### 1. Get Your OpenRouter API Key

Visit [openrouter.ai](https://openrouter.ai/) and:
1. Sign up for an account
2. Add credits or enable automatic top-up ($5 minimum recommended)
3. Generate an API key

**Pro Tip**: Have Azure, AWS, or GCP credits? Link them to OpenRouter to use existing cloud accounts!

### 2. Configure Your Synod (First Run)

Run the interactive configuration wizard:

```bash
synod config
```

You'll be prompted to:
1. **Enter your OpenRouter API key**
2. **Select your Bishops**: Choose from our 6 SOTA models (3-6 recommended for debate):
   - Claude Opus 4.5
   - Claude Sonnet 4.5
   - GPT 5.1 Chat
   - Grok 4.1 Fast
   - Gemini 3.0
   - DeepSeek V3.1
3. **Select your Pope**: Choose which Bishop will synthesize the final solution
   - Recommended: Claude Opus 4.5 (best at reasoning and synthesis)

Configuration is saved to `~/.synod/config.json` for future sessions.

## Usage

### Submit a Coding Query

```bash
synod query "Implement a concurrent task queue with priority scheduling"
```

**Note:** After answering your query, Synod automatically enters interactive mode (just like Claude Code). You can continue asking questions until you type `exit`.

### Interactive Mode & Slash Commands

Once in interactive mode, you have access to powerful slash commands:

```bash
# Session Management
synod> /help          # Show all available commands
synod> /exit          # Exit the Synod session (aliases: /quit, /q)
synod> /clear         # Clear conversation history (aliases: /reset, /new)
synod> /compact       # Compact conversation history to save context
synod> /history       # View recent session history
synod> /cost          # Show session cost breakdown
synod> /stats         # Show detailed usage statistics

# Configuration
synod> /config        # Open configuration panel (aliases: /settings)
synod> /bishops       # View or change your bishop models
synod> /pope          # View or change your pope model

# Workspace
synod> /files         # List indexed files in the workspace
synod> /index         # Re-index the current workspace (aliases: /reindex)
synod> /add           # Add files to the current context

# Debug & Info
synod> /context       # View Pope's context usage
synod> /version       # Show Synod version (aliases: /v)
```

Type `/` to see auto-complete suggestions for all commands.

### Provide File Context

Give Synod access to your existing code for context-aware solutions:

```bash
synod query "Refactor this function to use async/await" -f src/utils.py -f src/tasks.py
```

### Reconfigure Models

Change your Bishops or Pope at any time:

```bash
synod config
```

### Example Queries

```bash
# Architecture & Design
synod query "Design a rate-limiting middleware for FastAPI"

# Algorithm Optimization
synod query "Optimize this sorting algorithm for large datasets" -f algorithms.py

# Security Review
synod query "Review this authentication code for vulnerabilities" -f auth.py

# Refactoring
synod query "Refactor this class to use dependency injection" -f services.py
```

## The Vision

Synod aims to be a unique and versatile coding agent that:
- Tackles complex coding challenges through collective intelligence
- Reduces hallucinations through adversarial validation
- Leverages the strengths of multiple SOTA models through expertise weighting
- Provides a seamless, always-on developer experience like Claude Code
- Ensures quality through 6-layer quality control (strict classification, consensus detection, papal veto, evidence-based critiques, smart pairing, unbiased Pope)
- Adapts intelligently to query complexity (1-5 bishops, 1-5 rounds based on needs)
- Evolves as new models and techniques emerge

The council is always in session.

## Contributing

We welcome contributions! Synod is **open source** and community-driven under the MIT License.

### Ways to Contribute

| Type | How |
|------|-----|
| 🐛 **Bug Reports** | [Open an issue](https://github.com/KekwanuLabs/synod-cli/issues) with steps to reproduce |
| 💡 **Feature Requests** | [Open an issue](https://github.com/KekwanuLabs/synod-cli/issues) with your idea |
| 🔧 **Code Contributions** | Fork → Branch → PR (see below) |
| 📖 **Documentation** | Improvements to README, docstrings, or guides |
| ⭐ **Spread the Word** | Star the repo, share on social media |

### Development Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/synod-cli.git
cd synod-cli

# Install dependencies with uv
uv sync

# Install in editable mode for development
pip install -e .

# Run the CLI
synod

# Build package
uv build
```

### Pull Request Guidelines

1. **Fork** the repository and create a feature branch
2. **Write clear commit messages** describing your changes
3. **Test your changes** - run `synod` and verify functionality
4. **Update documentation** if you've added features
5. **Submit a PR** with a clear description of what and why

We aim to review PRs within a few days. For large changes, open an issue first to discuss.

## Roadmap

- [x] **v0.1.0** - Initial 3-stage debate system
- [x] **v0.2.0** - Intelligent debate, slash commands, interactive mode
  - Stage 0 classification, expertise weighting, consensus detection
  - Slash command system with auto-completion
  - Chat-style input with command history
  - Context management with auto-compacting
  - Syntax highlighting for code responses
- [x] **v0.3.0** - Enhanced adversarial debate & Active Pope (current)
  - Consensus-aware critique prompts (hunt blind spots vs pick winners vs arbitrate)
  - Smart skipping of redundant critiques (85%+ similar proposals)
  - Active Pope that ADDs, OVERRIDEs, and CHALLENGES (not just merges)
  - Improved UI with Pope observer indicator and skip display
  - Faster logo animation and cleaner stage panels
- [ ] **v0.4.0** - File system access (read, edit, create files like Claude Code)
- [ ] **v0.5.0** - VS Code extension
- [ ] **v0.6.0** - GitHub Action for PR reviews
- [ ] **v1.0.0** - Stable API, production-ready

## Community

- **GitHub**: [KekwanuLabs/synod-cli](https://github.com/KekwanuLabs/synod-cli)
- **Issues**: [Report bugs & feature requests](https://github.com/KekwanuLabs/synod-cli/issues)
- **PyPI**: [synod-cli](https://pypi.org/project/synod-cli/)

## License

**MIT License** - Synod is free and open source software.

You are free to:
- ✅ Use commercially
- ✅ Modify and distribute
- ✅ Use privately
- ✅ Sublicense

See [LICENSE](LICENSE) for the full text.

Copyright (c) 2025-present [KekwanuLabs](https://kekwanu.com)

---

<div align="center">

**Synod: Ancient Councils. Modern Intelligence. Open Source.**

⭐ [Star us on GitHub](https://github.com/KekwanuLabs/synod-cli) if you find Synod useful!

[Report Bug](https://github.com/KekwanuLabs/synod-cli/issues) · [Request Feature](https://github.com/KekwanuLabs/synod-cli/issues) · [PyPI](https://pypi.org/project/synod-cli/)

</div>
